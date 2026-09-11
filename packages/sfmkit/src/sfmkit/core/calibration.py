"""Camera calibration: from photographs of a chessboard, or from what EXIF says."""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

__all__ = ["Calibration", "calibrate_chessboard", "intrinsics_from_focal_35mm"]

# The diagonal of a full-frame, 36 x 24 mm, sensor.
FULL_FRAME_DIAGONAL_MM = math.hypot(36, 24)


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


def intrinsics_from_focal_35mm(focal_35mm: float, width: int, height: int,
                               sensor_aspect: float = 4 / 3) -> np.ndarray:
    """K from the 35 mm equivalent focal length that a photo's EXIF gives.

    The equivalent focal length is the one a full-frame camera would need for
    the same field of view across the sensor's diagonal. A phone's sensor is
    4:3, and a 16:9 photo is cut from it keeping the long side, so the diagonal
    is the whole sensor's, of ``sensor_aspect``, not the photo's. The principal
    point is put at the centre, with pixel centres at integers as OpenCV has
    them. No distortion: an estimate to reconstruct with until a chessboard
    calibration replaces it.
    """
    long_side = max(width, height)
    diagonal_px = math.hypot(long_side, long_side / sensor_aspect)
    f = focal_35mm / FULL_FRAME_DIAGONAL_MM * diagonal_px
    return np.array([[f, 0.0, (width - 1) / 2], [0.0, f, (height - 1) / 2], [0.0, 0.0, 1.0]])
