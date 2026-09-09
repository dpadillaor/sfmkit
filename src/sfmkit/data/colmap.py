"""Readers for COLMAP's text model format, used as an external reference."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from sfmkit.core.types import Pose

__all__ = ["read_cameras", "read_images", "read_points3d", "read_model"]


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
