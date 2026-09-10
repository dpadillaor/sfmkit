"""Chessboard calibration, on boards rendered through a known camera."""

import cv2
import numpy as np
import pytest

from sfmkit.core.calibration import calibrate_chessboard

K_TRUE = np.array([[800.0, 0, 320], [0, 800.0, 240], [0, 0, 1]])
PATTERN = (9, 6)
SQUARE, MARGIN = 40, 40  # pixels in the flat board image


def _board() -> np.ndarray:
    cols, rows = PATTERN[0] + 1, PATTERN[1] + 1
    img = np.full((rows * SQUARE + 2 * MARGIN, cols * SQUARE + 2 * MARGIN), 255, np.uint8)
    for r in range(rows):
        for c in range(cols):
            if (r + c) % 2 == 0:
                y, x = MARGIN + r * SQUARE, MARGIN + c * SQUARE
                img[y:y + SQUARE, x:x + SQUARE] = 0
    return img


def _view(board: np.ndarray, rvec, distance: float = 18.0) -> np.ndarray:
    """The board photographed from ``rvec``, looking at its centre."""
    R, _ = cv2.Rodrigues(np.asarray(rvec, float))
    centre = np.array([(PATTERN[0] - 1) / 2, (PATTERN[1] - 1) / 2, 0])
    t = np.array([0, 0, distance]) - R @ centre
    plane_to_image = K_TRUE @ np.column_stack([R[:, 0], R[:, 1], t])
    # Pixels of the flat board image to board units, with inner corner (0, 0) at the origin.
    o = -(MARGIN + SQUARE) / SQUARE
    pixel_to_plane = np.array([[1 / SQUARE, 0, o], [0, 1 / SQUARE, o], [0, 0, 1]])
    return cv2.warpPerspective(board, plane_to_image @ pixel_to_plane, (640, 480),
                               flags=cv2.INTER_LINEAR, borderValue=255)


def test_recovers_the_camera_that_rendered_the_boards():
    board = _board()
    tilts = [(0.3, 0, 0), (-0.3, 0, 0), (0, 0.3, 0), (0, -0.3, 0),
             (0.2, 0.25, 0.1), (-0.25, 0.2, -0.1)]
    cal = calibrate_chessboard([_view(board, r) for r in tilts], PATTERN)

    assert cal.used == list(range(len(tilts)))
    assert cal.rmse < 0.2
    assert cal.K[0, 0] == pytest.approx(800, rel=0.005)
    assert cal.K[1, 1] == pytest.approx(800, rel=0.005)
    assert cal.K[:2, 2] == pytest.approx([320, 240], abs=2)


def test_images_without_a_board_are_skipped():
    board = _board()
    blank = np.full((480, 640), 255, np.uint8)
    views = [_view(board, r) for r in [(0.3, 0, 0), (0, 0.3, 0), (-0.2, -0.2, 0)]]
    cal = calibrate_chessboard([blank, *views], PATTERN)
    assert cal.used == [1, 2, 3]


def test_too_few_boards_is_an_error():
    blank = np.full((480, 640), 255, np.uint8)
    with pytest.raises(ValueError, match="need 3"):
        calibrate_chessboard([blank] * 4, PATTERN)
