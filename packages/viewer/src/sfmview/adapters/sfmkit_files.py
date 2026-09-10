"""sfmkit's own results, read into a ``Model``.

``reconstruct/reconstruction.npz`` holds K, the poses and the points;
``localize/query_pose.npz`` the old photo's pose, and its K when the run
recorded it. The keys are part of the contract in ``docs/viewer.md``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from sfmview.domain import Camera, Model


def read_reconstruction(path, query_pose=None, query: str | None = None) -> Model:
    """The reconstruction in ``path``, with the query's pose if one is given."""
    with np.load(Path(path), allow_pickle=False) as d:
        K = d["K"]
        size = _size(K)
        cameras = [Camera(str(n), R, t, K, size)
                   for n, R, t in zip(d["image_names"], d["rotations"], d["translations"],
                                      strict=True)]
        points = d["points"].reshape(-1, 3)
        colors = d["colors"].astype(np.uint8) if "colors" in d.files else None

    if query and query_pose is not None and Path(query_pose).is_file():
        with np.load(Path(query_pose), allow_pickle=False) as q:
            K_q = q["K"] if "K" in q.files else None
            cameras.append(Camera(query, q["R"], q["t"], K_q, _size(K_q), query=True))
    return Model("sfmkit", tuple(cameras), points, colors)


def _size(K: np.ndarray | None) -> tuple[int, int] | None:
    """The image size, guessed from a principal point at the centre.

    sfmkit does not record image sizes; a camera's outline only needs its shape.
    """
    if K is None:
        return None
    return round(2 * K[0, 2]), round(2 * K[1, 2])
