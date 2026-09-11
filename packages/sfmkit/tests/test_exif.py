from pathlib import Path

import pytest
from PIL import Image

from sfmkit.data.exif import read_camera

SCENE = Path(__file__).resolve().parents[3] / "data" / "valencia" / "scene"


def photo(path, **tags):
    exif = Image.Exif()
    exif[0x0110] = "Phone X"
    ifd = exif.get_ifd(0x8769)
    for tag, value in tags.items():
        ifd[{"focal": 0x920A, "focal_35mm": 0xA405}[tag]] = value
    Image.new("RGB", (64, 36)).save(path, exif=exif)
    return path


def test_the_camera_settings_are_read(tmp_path):
    shot = read_camera(photo(tmp_path / "a.jpg", focal=5.4, focal_35mm=26))
    assert shot.model == "Phone X" and shot.focal_35mm == 26 and shot.focal_mm == 5.4
    assert shot.size == (64, 36)


def test_a_photo_without_the_equivalent_focal_length_is_refused(tmp_path):
    with pytest.raises(ValueError, match="35 mm"):
        read_camera(photo(tmp_path / "a.jpg", focal=5.4))


@pytest.mark.skipif(not (SCENE / "Img02.jpg").is_file(), reason="no Valencia photos")
def test_the_valencia_photos():
    shot = read_camera(SCENE / "Img02.jpg")
    assert (shot.model, shot.focal_35mm, shot.size) == ("SM-G996B", 26, (4032, 2268))
