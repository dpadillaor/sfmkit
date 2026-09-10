"""Reading COLMAP's text models."""

import numpy as np
import pytest

from sfmkit.data.colmap import intrinsics, read_images, read_model

IMAGES = """\
# Image list with two lines of data per image:
1 1 0 0 0 0.5 0 0 1 Img02
10.0 20.0 -1 30.0 40.0 7
2 1 0 0 0 0 0.25 0 2 Img00

3 1 0 0 0 1 0 0 1 Img13
5.0 6.0 -1
"""


def test_an_image_without_points_does_not_shift_the_rest(tmp_path):
    """Img00's second line is empty; the reader must not pair Img13 with it."""
    (tmp_path / "images.txt").write_text(IMAGES)
    poses = read_images(tmp_path / "images.txt")
    assert list(poses) == ["Img02", "Img00", "Img13"]
    assert poses["Img13"].t == pytest.approx([1, 0, 0])


def test_the_model_says_which_camera_took_each_image(tmp_path):
    (tmp_path / "images.txt").write_text(IMAGES)
    (tmp_path / "cameras.txt").write_text("1 PINHOLE 4032 2268 3543 3544 2054 1123\n"
                                          "2 SIMPLE_RADIAL 557 418 602 278.5 209 0.1\n")
    (tmp_path / "points3D.txt").write_text("1 0 0 5 255 0 0 0.5 1 0\n")
    model = read_model(tmp_path)
    assert model["image_cameras"] == {"Img02": 1, "Img00": 2, "Img13": 1}
    old = intrinsics(model["cameras"][2])
    assert (old["fx"], old["fy"], old["cx"], old["cy"]) == (602, 602, 278.5, 209)
    phone = intrinsics(model["cameras"][1])
    assert np.allclose([phone[k] for k in ("fx", "fy", "cx", "cy")], [3543, 3544, 2054, 1123])
