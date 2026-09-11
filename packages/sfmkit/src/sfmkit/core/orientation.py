"""A photo's EXIF orientation: the turn that shows it upright, and back.

A phone stores a photo taken upright as its sensor saw it, sideways, and says
in the EXIF how to turn it for showing. Features are found on the photo
upright, as SuperPoint and LightGlue are not rotation invariant: turned, an
upright photo matches a level one barely at all. Geometry is done on the
pixels as stored, whose K the EXIF gives, so keypoints go back there.
"""

from __future__ import annotations

import numpy as np

__all__ = ["to_stored", "upright"]


def upright(image: np.ndarray, orientation: int) -> np.ndarray:
    """``image``, as stored, turned as EXIF ``orientation`` (1 to 8) says to show it."""
    turns = {
        1: lambda s: s,
        2: lambda s: s[:, ::-1],
        3: lambda s: s[::-1, ::-1],
        4: lambda s: s[::-1, :],
        5: lambda s: s.swapaxes(0, 1),
        6: lambda s: np.rot90(s, -1),  # a quarter clockwise
        7: lambda s: np.rot90(s[:, ::-1], -1),
        8: lambda s: np.rot90(s, 1),
    }
    return turns.get(orientation, turns[1])(image)


def to_stored(points: np.ndarray, orientation: int, size: tuple[int, int]) -> np.ndarray:
    """``(N, 2)`` pixel positions on the upright photo, on the photo as stored.

    ``size`` is the stored photo's width and height; positions are pixel
    indices, the first pixel's centre at 0.
    """
    p = np.asarray(points, dtype=float).reshape(-1, 2)
    x, y = p[:, 0], p[:, 1]
    w, h = size[0] - 1, size[1] - 1
    back = {
        1: (x, y), 2: (w - x, y), 3: (w - x, h - y), 4: (x, h - y),
        5: (y, x), 6: (y, h - x), 7: (w - y, h - x), 8: (w - y, x),
    }
    return np.column_stack(back.get(orientation, back[1]))
