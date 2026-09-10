"""COLMAP, the external reference: read its text models, and run it."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pycolmap

from sfmkit.core.types import Pose
from sfmkit.data.io import image_file

__all__ = [
    "ColmapSummary", "read_cameras", "read_images", "read_points3d", "read_model", "run_colmap",
]


@dataclass
class ColmapSummary:
    """What a COLMAP run registered, for the stage to report.

    It stands in for pycolmap's own Reconstruction, which stays in this module.
    """

    registered: list[str]  # image names, without extension
    missing: list[str]  # asked for, but not registered
    n_points: int
    reprojection_error: float  # mean, in pixels


def _quaternion_to_rotation(q: np.ndarray) -> np.ndarray:
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def _lines(path: Path):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                yield line


def read_cameras(path) -> dict[int, dict]:
    """Read ``cameras.txt``: camera id to model, size and parameters.

    The meaning of ``params`` depends on ``model``; for SIMPLE_RADIAL it is
    focal length, principal point and one distortion coefficient.
    """
    out = {}
    for line in _lines(Path(path)):
        p = line.split()
        out[int(p[0])] = {
            "model": p[1],
            "width": int(p[2]),
            "height": int(p[3]),
            "params": np.array([float(v) for v in p[4:]]),
        }
    return out


def read_images(path) -> dict[str, Pose]:
    """Image name to world-to-camera pose. COLMAP's convention matches ours."""
    out: dict[str, Pose] = {}
    rows = list(_lines(Path(path)))
    for i in range(0, len(rows), 2):  # every second line holds the 2D points
        p = rows[i].split()
        q = np.array([float(v) for v in p[1:5]])
        t = np.array([float(v) for v in p[5:8]])
        out[p[9]] = Pose(_quaternion_to_rotation(q), t)
    return out


def read_points3d(path) -> tuple[np.ndarray, np.ndarray]:
    """Read ``points3D.txt``, returning ``(N, 3)`` positions and RGB colours."""
    xyz, rgb = [], []
    for line in _lines(Path(path)):
        p = line.split()
        xyz.append([float(v) for v in p[1:4]])
        rgb.append([int(v) for v in p[4:7]])
    return np.asarray(xyz, dtype=float), np.asarray(rgb, dtype=float)


def read_model(directory) -> dict:
    """Read a whole COLMAP text model: cameras, poses, points and colours."""
    d = Path(directory)
    xyz, rgb = read_points3d(d / "points3D.txt")
    return {
        "cameras": read_cameras(d / "cameras.txt"),
        "poses": read_images(d / "images.txt"),
        "points": xyz,
        "colors": rgb,
    }


def run_colmap(scene_dir, images: list[str], out_dir) -> ColmapSummary:
    """COLMAP on its own: SIFT features, exhaustive matching, incremental mapping.

    Reconstructs ``images`` from ``scene_dir`` with one self-calibrated camera
    for all of them, and writes the largest model as text into ``out_dir``,
    beside COLMAP's database. The model names images as sfmkit does, without
    extension.
    """
    pycolmap.logging.minloglevel = pycolmap.logging.ERROR  # ~100 lines of progress otherwise
    scene_dir, out_dir = Path(scene_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # COLMAP names an image by its file; sfmkit, without extension.
    names = {image_file(scene_dir, n).name: n for n in images}
    database = out_dir / "database.db"
    database.unlink(missing_ok=True)

    pycolmap.extract_features(database, scene_dir, image_names=list(names),
                              camera_mode=pycolmap.CameraMode.SINGLE)
    pycolmap.match_exhaustive(database)
    with tempfile.TemporaryDirectory() as sparse:
        models = pycolmap.incremental_mapping(database, scene_dir, sparse)
    if not models:
        raise RuntimeError(f"COLMAP registered none of the {len(images)} images")
    rec = max(models.values(), key=lambda r: r.num_reg_images())

    for image in rec.images.values():
        image.name = names[image.name]
    rec.write_text(out_dir)

    registered = sorted(image.name for image in rec.images.values() if image.has_pose)
    return ColmapSummary(
        registered=registered,
        missing=sorted(set(images) - set(registered)),
        n_points=rec.num_points3D(),
        reprojection_error=rec.compute_mean_reprojection_error(),
    )
