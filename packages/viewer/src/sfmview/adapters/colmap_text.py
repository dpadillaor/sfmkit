"""COLMAP's text model, read into a ``Model``: cameras.txt, images.txt, points3D.txt.

sfmkit writes these for every run (its ``colmap`` stage), naming images as it
does, without extension.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from sfmview.domain import Camera, Model

# Camera models whose parameters open with one focal length for both axes; the
# others open with fx, fy. Then come cx, cy.
_ONE_FOCAL = {"SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL", "SIMPLE_RADIAL_FISHEYE",
              "RADIAL_FISHEYE"}


def read_colmap(directory, query: str | None = None) -> Model:
    """The model in ``directory``; ``query`` names the photo placed afterwards."""
    d = Path(directory)
    intrinsics = _cameras(d / "cameras.txt")
    cameras = tuple(
        Camera(name, R, t, *intrinsics.get(camera_id, (None, None)), query=name == query)
        for name, R, t, camera_id in _images(d / "images.txt")
    )
    points, colors = _points(d / "points3D.txt")
    return Model("colmap", cameras, points, colors)


def _rows(path: Path) -> list[str]:
    with open(path) as f:
        return [line.strip() for line in f if not line.startswith("#")]


def _cameras(path: Path) -> dict[int, tuple[np.ndarray, tuple[int, int]]]:
    """Camera id to ``(K, (width, height))``."""
    out = {}
    for row in filter(None, _rows(path)):
        p = row.split()
        model, width, height = p[1], int(p[2]), int(p[3])
        params = [float(v) for v in p[4:]]
        if model in _ONE_FOCAL:
            fx = fy = params[0]
            cx, cy = params[1:3]
        else:
            fx, fy, cx, cy = params[:4]
        out[int(p[0])] = (np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]]), (width, height))
    return out


def _images(path: Path):
    """``(name, R, t, camera id)`` per image.

    Each image takes two lines; the second, its 2D points, is empty when it has
    none, so empty lines are kept rather than skipped.
    """
    rows = _rows(path)
    for i in range(0, len(rows) - 1, 2):
        p = rows[i].split()
        q = np.array([float(v) for v in p[1:5]])
        t = np.array([float(v) for v in p[5:8]])
        yield p[9], _rotation(q), t, int(p[8])


def _rotation(q: np.ndarray) -> np.ndarray:
    """COLMAP's quaternion (w, x, y, z) as a rotation matrix."""
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def _points(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """``(N, 3)`` positions and ``(N, 3)`` uint8 colours."""
    rows = [row.split() for row in filter(None, _rows(path))]
    xyz = np.array([[float(v) for v in p[1:4]] for p in rows]).reshape(-1, 3)
    rgb = np.array([[int(v) for v in p[4:7]] for p in rows], dtype=np.uint8).reshape(-1, 3)
    return xyz, rgb
