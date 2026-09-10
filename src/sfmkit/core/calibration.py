"""Camera calibration from photographs of a chessboard."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

__all__ = ["Calibration", "calibrate_chessboard"]


@dataclass(eq=False)
class Calibration:
    """Intrinsics and distortion, and which images the board was found in."""

    K: np.ndarray
    dist: np.ndarray
    rmse: float  # reprojection error over every detected corner, in pixels
    used: list[int]


def calibrate_chessboard(images: list[np.ndarray], pattern: tuple[int, int]) -> Calibration:
    """Calibrate from grayscale photos of a board with ``pattern`` inner corners.

    Photos where the board is not found are skipped. The square size is not
    needed: it scales the board's poses, not ``K``.
    """
    cols, rows = pattern
    board = np.zeros((cols * rows, 3), np.float32)
    board[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3)

    object_points, image_points, used = [], [], []
    for i, img in enumerate(images):
        found, corners = cv2.findChessboardCorners(img, (cols, rows))
        if not found:
            continue
        corners = cv2.cornerSubPix(img, corners, (11, 11), (-1, -1), criteria)
        object_points.append(board)
        image_points.append(corners)
        used.append(i)
    if len(used) < 3:
        raise ValueError(f"board found in {len(used)} of {len(images)} images; need 3")

    h, w = images[0].shape[:2]
    rmse, K, dist, _, _ = cv2.calibrateCamera(object_points, image_points, (w, h), None, None)
    return Calibration(K=K, dist=dist.ravel(), rmse=float(rmse), used=used)
