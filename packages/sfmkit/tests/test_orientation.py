"""A photo turned upright as its EXIF says, and its pixels found back as stored."""

import numpy as np
import pytest
from PIL import Image, ImageOps

from sfmkit.core.orientation import to_stored, upright
from sfmkit.data.exif import read_orientation


@pytest.mark.parametrize("orientation", range(1, 9))
def test_upright_is_how_a_viewer_shows_it(tmp_path, orientation):
    stored = np.random.default_rng(orientation).integers(0, 255, (5, 8, 3), dtype=np.uint8)
    exif = Image.Exif()
    exif[0x0112] = orientation
    Image.fromarray(stored).save(tmp_path / "a.png", exif=exif)
    with Image.open(tmp_path / "a.png") as im:
        shown = np.asarray(ImageOps.exif_transpose(im))  # Pillow, as a viewer would
    assert read_orientation(tmp_path / "a.png") == orientation
    assert np.array_equal(upright(stored, orientation), shown)


@pytest.mark.parametrize("orientation", range(1, 9))
def test_every_upright_pixel_goes_back_to_where_it_was_stored(orientation):
    stored = np.arange(5 * 8).reshape(5, 8)  # each pixel its own value
    shown = upright(stored, orientation)
    ys, xs = np.mgrid[:shown.shape[0], :shown.shape[1]]
    back = to_stored(np.column_stack([xs.ravel(), ys.ravel()]), orientation, (8, 5)).astype(int)
    assert np.array_equal(stored[back[:, 1], back[:, 0]], shown.ravel())


def test_no_orientation_is_as_stored(tmp_path):
    Image.new("RGB", (4, 3)).save(tmp_path / "plain.jpg")
    assert read_orientation(tmp_path / "plain.jpg") == 1
