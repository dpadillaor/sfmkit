"""Read and write run artefacts: matches, reconstructions and manifests."""

from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from sfmkit.core.types import Matches, Pose, Reconstruction, Track

__all__ = [
    "load_matches_npz", "save_matches", "load_matches", "save_reconstruction",
    "load_reconstruction", "write_manifest", "read_manifest",
]


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=True
        ).stdout.strip()
    except Exception:
        return None


def write_manifest(run_dir, stage: str, config, extra: dict | None = None,
                   config_path: str | None = None) -> Path:
    """Record what produced this run: config, commit, versions, timestamp.

    ``config_path`` is recorded as well as the config's contents, so that a tool
    reading a run back can re-invoke the same stage without guessing where the
    file lives.
    """
    stage_dir = Path(run_dir) / stage
    stage_dir.mkdir(parents=True, exist_ok=True)
    import scipy

    import sfmkit

    payload = {
        "stage": stage,
        "config_path": config_path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "config": asdict(config) if is_dataclass(config) else dict(config or {}),
        "versions": {
            "sfmkit": sfmkit.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "python": platform.python_version(),
        },
        **(extra or {}),
    }
    path = stage_dir / "manifest.json"
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def read_manifest(run_dir, stage: str) -> dict:
    """Read back the manifest a stage wrote."""
    return json.loads((Path(run_dir) / stage / "manifest.json").read_text())


def load_matches_npz(path, image0: str, image1: str) -> Matches:
    """Read a LightGlue-style ``.npz`` of keypoints and matches."""
    with np.load(Path(path)) as d:
        pairs = d["matches"]
        inliers = d["inliers"] if "inliers" in d.files else None
        # Older files stored surviving pairs rather than a mask.
        if inliers is None and "inliers_matches" in d.files:
            surviving = {tuple(r) for r in d["inliers_matches"]}
            inliers = np.array([tuple(r) in surviving for r in pairs], dtype=bool)
        return Matches(
            image0=image0,
            image1=image1,
            keypoints0=d["keypoints0"],
            keypoints1=d["keypoints1"],
            pairs=pairs,
            scores=d["scores"] if "scores" in d.files else None,
            inliers=inliers,
        )


def save_matches(matches: Matches, path) -> None:
    """Write matches to a compressed ``.npz``. Optional fields are omitted."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "keypoints0": matches.keypoints0,
        "keypoints1": matches.keypoints1,
        "matches": matches.pairs,
        "image0": np.array(matches.image0),
        "image1": np.array(matches.image1),
    }
    if matches.scores is not None:
        payload["scores"] = matches.scores
    if matches.inliers is not None:
        payload["inliers"] = matches.inliers
    np.savez_compressed(path, **payload)


def load_matches(path) -> Matches:
    """Read matches written by ``save_matches``."""
    with np.load(Path(path), allow_pickle=False) as d:
        return Matches(
            image0=str(d["image0"]),
            image1=str(d["image1"]),
            keypoints0=d["keypoints0"],
            keypoints1=d["keypoints1"],
            pairs=d["matches"],
            scores=d["scores"] if "scores" in d.files else None,
            inliers=d["inliers"] if "inliers" in d.files else None,
        )


def save_reconstruction(rec: Reconstruction, path) -> None:
    """Poses, points and tracks in one npz plus a readable JSON sidecar."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    names = list(rec.poses)
    np.savez_compressed(
        path,
        K=rec.K,
        image_names=np.array(names),
        rotations=np.stack([rec.poses[n].R for n in names]) if names else np.zeros((0, 3, 3)),
        translations=np.stack([rec.poses[n].t for n in names]) if names else np.zeros((0, 3)),
        points=rec.points,
        track_images=np.array([json.dumps(t.observations) for t in rec.tracks]),
    )
    path.with_suffix(".json").write_text(json.dumps({
        "n_cameras": len(names),
        "images": names,
        "n_points": rec.n_points,
        "n_tracks": len(rec.tracks),
        "K": rec.K.tolist(),
        "poses": {n: {"R": rec.poses[n].R.tolist(), "t": rec.poses[n].t.tolist()} for n in names},
    }, indent=2))


def load_reconstruction(path) -> Reconstruction:
    """Read a reconstruction written by ``save_reconstruction``."""
    with np.load(Path(path), allow_pickle=False) as d:
        names = [str(n) for n in d["image_names"]]
        poses = {n: Pose(d["rotations"][i], d["translations"][i]) for i, n in enumerate(names)}
        tracks = [Track(observations=json.loads(str(s))) for s in d["track_images"]]
        return Reconstruction(K=d["K"], poses=poses, points=d["points"], tracks=tracks)
