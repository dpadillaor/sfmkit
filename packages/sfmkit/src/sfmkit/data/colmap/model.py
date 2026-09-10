"""Read COLMAP's text models: cameras, image poses and points."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from sfmkit.core.types import Pose

__all__ = ["intrinsics", "read_cameras", "read_images", "read_points3d", "read_model"]

# Camera models whose parameters open with a single focal length, shared by both
# axes; the others open with fx, fy.
_ONE_FOCAL = {"SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL", "SIMPLE_RADIAL_FISHEYE",
              "RADIAL_FISHEYE"}


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

    The meaning of ``params`` depends on ``model``; ``intrinsics`` reads the
    focal lengths and principal point out of them.
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


def intrinsics(camera: dict) -> dict[str, float]:
    """Focal lengths and principal point of a camera from ``read_cameras``."""
    p = camera["params"]
    if camera["model"] in _ONE_FOCAL:
        return {"fx": float(p[0]), "fy": float(p[0]), "cx": float(p[1]), "cy": float(p[2])}
    return {"fx": float(p[0]), "fy": float(p[1]), "cx": float(p[2]), "cy": float(p[3])}


def _images(path: Path):
    """``(name, pose, camera id)`` per image.

    Each image takes two lines; the second, its 2D points, is empty when it has
    none, so empty lines are kept rather than skipped.
    """
    with open(path) as f:
        rows = [line.strip() for line in f if not line.startswith("#")]
    for i in range(0, len(rows) - 1, 2):
        p = rows[i].split()
        q = np.array([float(v) for v in p[1:5]])
        t = np.array([float(v) for v in p[5:8]])
        yield p[9], Pose(_quaternion_to_rotation(q), t), int(p[8])


def read_images(path) -> dict[str, Pose]:
    """Image name to world-to-camera pose. COLMAP's convention matches ours."""
    return {name: pose for name, pose, _ in _images(Path(path))}


def read_points3d(path) -> tuple[np.ndarray, np.ndarray]:
    """Read ``points3D.txt``, returning ``(N, 3)`` positions and RGB colours."""
    xyz, rgb = [], []
    for line in _lines(Path(path)):
        p = line.split()
        xyz.append([float(v) for v in p[1:4]])
        rgb.append([int(v) for v in p[4:7]])
    return np.asarray(xyz, dtype=float), np.asarray(rgb, dtype=float)


def read_model(directory) -> dict:
    """Read a whole COLMAP text model: cameras, poses, points and colours.

    ``image_cameras`` says which camera each image was taken with.
    """
    d = Path(directory)
    xyz, rgb = read_points3d(d / "points3D.txt")
    images = list(_images(d / "images.txt"))
    return {
        "cameras": read_cameras(d / "cameras.txt"),
        "poses": {name: pose for name, pose, _ in images},
        "image_cameras": {name: camera for name, _, camera in images},
        "points": xyz,
        "colors": rgb,
    }
