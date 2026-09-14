"""The old photo refined in a model made elsewhere, its principal point freed."""

import shutil
from pathlib import Path

import numpy as np
import pytest

from sfmkit.data.colmap import intrinsics, read_model, refine_query

REPO = Path(__file__).resolve().parents[3]
PRECOMPUTED = REPO / "projects" / "valencia" / "data" / "precomputed"
COURSE = PRECOMPUTED / "colmap" / "9cameras_sfmkit_matches"


@pytest.fixture
def model(tmp_path):
    for name in ("cameras.txt", "images.txt", "points3D.txt"):
        shutil.copyfile(COURSE / name, tmp_path / name)
    return tmp_path


def test_only_the_old_photo_moves(model):
    before = read_model(model)
    (x0, y0), (x1, y1) = refine_query(model, "Img00")
    after = read_model(model)
    assert (x0, y0) == (278.5, 209)  # pinned at the centre of its 557x418
    assert y1 > y0 + 50  # the shifted lens: well below it
    old = [c for n, c in before["image_cameras"].items() if n == "Img00"][0]
    assert intrinsics(after["cameras"][old])["cy"] == pytest.approx(y1)
    for name, pose in before["poses"].items():
        if name != "Img00":
            assert np.allclose(after["poses"][name].R, pose.R)
            assert np.allclose(after["poses"][name].t, pose.t)
    for camera, c in before["cameras"].items():
        if camera != old:
            assert np.array_equal(after["cameras"][camera]["params"], c["params"])
    assert np.allclose(after["points"], before["points"])


def test_a_model_without_the_photo_is_left_alone(model):
    assert refine_query(model, "Img99") is None


def test_a_shared_camera_is_refused(model):
    images = model / "images.txt"
    lines = images.read_text().splitlines()
    for i, line in enumerate(lines):
        fields = line.split()
        if len(fields) == 10 and fields[9].startswith("Img00"):
            fields[8] = "2"  # the phone's camera
            lines[i] = " ".join(fields)
    images.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="shares its camera"):
        refine_query(model, "Img00")
