"""Reading runs off disk. No Textual imports here, so it stays testable."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

STAGES = ["calibrate", "match", "verify", "reconstruct", "localize", "colmap", "dense",
          "evaluate", "changes", "figures"]


@dataclass
class RunSummary:
    """Everything the interface needs about one run directory."""

    path: Path
    name: str
    stages: dict[str, dict] = field(default_factory=dict)

    @property
    def completed(self) -> list[str]:
        return [s for s in STAGES if s in self.stages]

    @property
    def config_name(self) -> str:
        for s in self.stages.values():
            n = (s.get("config") or {}).get("name")
            if n:
                return n
        return "-"

    @property
    def config_path(self) -> str | None:
        """Where the config that produced this run lives, if it was recorded."""
        for stage in reversed(STAGES):
            node = self.stages.get(stage)
            if node and node.get("config_path"):
                return node["config_path"]
        return None

    @property
    def timestamp(self) -> str:
        times = [s.get("timestamp", "") for s in self.stages.values()]
        return max(times)[:19].replace("T", " ") if times else "-"

    @property
    def commit(self) -> str:
        for s in self.stages.values():
            if s.get("git_commit"):
                return s["git_commit"][:8]
        return "-"

    def metric(self, *path, default=None):
        """Look a key up across all stage manifests, most recent stage winning."""
        for stage in reversed(STAGES):
            node = self.stages.get(stage)
            if node is None:
                continue
            for key in path:
                if not isinstance(node, dict) or key not in node:
                    node = None
                    break
                node = node[key]
            if node is not None:
                return node
        return default

    @property
    def headline(self) -> dict:
        return {
            "cameras": self.metric("n_cameras", default="-"),
            "points": self.metric("n_points", default="-"),
            "tracks": self.metric("tracks", "n_tracks", default="-"),
            "mean_rot": self.metric("mean_rotation_error_deg", default=None),
            "scale": self.metric("scale", default=None),
        }


def load_runs(root: Path | str = "runs") -> list[RunSummary]:
    """Every directory under ``root`` holding at least one ``<stage>/manifest.json``.

    Runs may be nested (``runs/<dataset>/<config>``); a run is named by its path
    relative to ``root``.
    """
    root = Path(root)
    if not root.is_dir():
        return []
    found: dict[Path, dict[str, dict]] = {}
    for f in sorted(root.glob("**/manifest.json")):
        stage = f.parent.name
        if stage not in STAGES:
            continue
        try:
            found.setdefault(f.parent.parent, {})[stage] = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
    out = [RunSummary(path=d, name=d.relative_to(root).as_posix(), stages=s)
           for d, s in found.items()]
    return sorted(out, key=lambda r: r.timestamp, reverse=True)


def compare(a: RunSummary, b: RunSummary) -> list[tuple[str, str, str]]:
    """Rows of (field, a, b) for the fields worth comparing between two runs."""
    fields = [
        ("config", lambda r: r.config_name),
        ("commit", lambda r: r.commit),
        ("stages", lambda r: ", ".join(r.completed)),
        ("cameras", lambda r: r.headline["cameras"]),
        ("3D points", lambda r: r.headline["points"]),
        ("tracks", lambda r: r.headline["tracks"]),
        ("observations", lambda r: r.metric("n_observations", default="-")),
        ("mean track length", lambda r: r.metric("tracks", "mean_length", default="-")),
        ("verified pairs", lambda r: r.metric("n_kept", default="-")),
        ("mean rot err (deg)", lambda r: r.headline["mean_rot"]),
        ("max rot err (deg)", lambda r: r.metric("max_rotation_error_deg", default="-")),
        ("query rot err (deg)", lambda r: r.metric("query_rotation_error_deg", default="-")),
        ("scale vs COLMAP", lambda r: r.headline["scale"]),
        ("query RMSE (px)", lambda r: r.metric("rmse_median", default="-")),
    ]
    rows = []
    for label, fn in fields:
        va, vb = fn(a), fn(b)
        fmt = lambda v: f"{v:.4f}" if isinstance(v, float) else str(v)  # noqa: E731
        rows.append((label, fmt(va), fmt(vb)))
    return rows
