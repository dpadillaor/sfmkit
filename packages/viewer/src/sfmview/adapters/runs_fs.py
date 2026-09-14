"""A ``RunStore`` over sfmkit's runs directory, ``<root>/<project>/<config>/<stage>/``.

Read-only: the viewer never writes into a run.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from sfmview.adapters.colmap_text import read_colmap
from sfmview.adapters.sfmkit_files import read_reconstruction
from sfmview.domain import Model, RunId, RunNotFound, RunSummary, Scene, assemble_scene

# What a run list shows of a run's evaluation, from evaluate's manifest.
METRICS = ("mean_rotation_error_deg", "max_rotation_error_deg", "n_cameras",
           "query_rotation_error_deg")


class FsRunStore:
    """Runs as sfmkit writes them: ``<root>/<project>/runs/<config>/``."""

    def __init__(self, root) -> None:
        self.root = Path(root).resolve()

    def runs(self) -> list[RunSummary]:
        found = []
        for manifest in self.root.glob("*/runs/*/*/manifest.json"):
            run_dir = manifest.parent.parent
            try:
                found.append(RunId(run_dir.parents[1].name, run_dir.name))
            except ValueError:
                continue
        summaries = [self._summary(run) for run in set(found)]
        return sorted(summaries, key=lambda s: s.updated or "", reverse=True)

    def scene(self, run: RunId) -> Scene:
        d = self._dir(run)
        manifests = _manifests(d)
        if not manifests:
            raise RunNotFound(str(run))
        config = next(iter(manifests.values())).get("config", {})
        query = (config.get("localize") or {}).get("query")
        evaluation = {}
        if _current(manifests, "evaluate"):
            evaluation = _json(d / "evaluate" / "evaluation.json") or {}
        query_pose = d / "localize" / "query_pose.npz" if _current(manifests, "localize") else None

        theirs = read_colmap(d / "colmap", query) if _has_colmap(d) else None
        ours = None
        if (d / "reconstruct" / "reconstruction.npz").is_file():
            ours = read_reconstruction(d / "reconstruct" / "reconstruction.npz", query_pose, query)
            if theirs is not None:
                ours = _sizes_from(ours, theirs)
        if ours is None and theirs is None:
            raise RunNotFound(f"{run} has no reconstruction yet")

        reference = evaluation.get("reference") or (config.get("sfm") or {}).get("reference")
        return assemble_scene(run, ours, theirs, reference=reference,
                              scale_image=evaluation.get("scale_image"),
                              dense=(d / "dense" / "fused.ply").is_file(),
                              dataset=config.get("dataset") or run.project)

    def dense_file(self, run: RunId) -> Path:
        path = self._dir(run) / "dense" / "fused.ply"
        if not path.is_file() or not path.resolve().is_relative_to(self.root):
            raise RunNotFound(f"{run} has no dense cloud")
        return path

    def _dir(self, run: RunId) -> Path:
        d = self.root / run.project / "runs" / run.config
        # RunId already refuses "..": this also refuses a symlink out of the root.
        if not d.is_dir() or not d.resolve().is_relative_to(self.root):
            raise RunNotFound(str(run))
        return d

    def _summary(self, run: RunId) -> RunSummary:
        d = self.root / run.project / "runs" / run.config
        manifests = _manifests(d)
        evaluated = manifests.get("evaluate", {})
        layers = [name for name, there in (
            ("sfmkit", (d / "reconstruct" / "reconstruction.npz").is_file()),
            ("colmap", _has_colmap(d)),
            ("dense", (d / "dense" / "fused.ply").is_file()),
        ) if there]
        return RunSummary(
            run=run,
            stages=tuple(sorted(manifests)),
            updated=max((m.get("timestamp", "") for m in manifests.values()), default=None),
            metrics={k: evaluated[k] for k in METRICS if k in evaluated},
            layers=tuple(layers),
            # Where the stages that can use a GPU ran, as their manifests say.
            devices={stage: m["device"] for stage, m in manifests.items()
                     if isinstance(m.get("device"), str)},
        )


def _manifests(run_dir: Path) -> dict[str, dict]:
    """Stage name to its manifest."""
    out = {}
    for path in sorted(run_dir.glob("*/manifest.json")):
        m = _json(path)
        if m is not None:
            out[m.get("stage", path.parent.name)] = m
    return out


def _current(manifests: dict[str, dict], stage: str) -> bool:
    """Whether ``stage`` ran on the reconstruction there is now.

    localize and evaluate work on a reconstruction: after reconstruct runs
    again, and until they do, their outputs describe the one before.
    """
    built = manifests.get("reconstruct", {}).get("timestamp", "")
    return stage in manifests and manifests[stage].get("timestamp", "") >= built


def _json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _has_colmap(run_dir: Path) -> bool:
    return all((run_dir / "colmap" / f).is_file()
               for f in ("cameras.txt", "images.txt", "points3D.txt"))


def _sizes_from(ours: Model, theirs: Model) -> Model:
    """``ours`` with each camera's image size taken from ``theirs``, which records it.

    sfmkit records no sizes, and the guess from K fails for the old photo, whose
    principal point DLT puts far from the centre.
    """
    cameras = []
    for c in ours.cameras:
        other = theirs.camera(c.name)
        cameras.append(replace(c, size=other.size) if other is not None and other.size else c)
    return replace(ours, cameras=tuple(cameras))
