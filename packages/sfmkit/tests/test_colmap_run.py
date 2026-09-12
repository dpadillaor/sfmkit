"""COLMAP run through pycolmap, on four of the Valencia photos and the old one."""

from pathlib import Path

import numpy as np
import pytest

from sfmkit.data import io
from sfmkit.data.colmap import (
    colmap_device,
    intrinsics,
    read_model,
    run_colmap,
    run_colmap_on_matches,
)

pytestmark = pytest.mark.slow

REPO = Path(__file__).resolve().parents[3]
SCENE = REPO / "data" / "valencia" / "scene"
EXAMPLE = REPO / "examples" / "valencia" / "cpu"
IMAGES = ["Img01", "Img14", "Img04", "Img05"]  # the four the old photo matches best
K = np.loadtxt(EXAMPLE / "calibrate" / "K.txt")


def _cameras(out):
    model = read_model(out)
    return model, {n: intrinsics(model["cameras"][c]) for n, c in model["image_cameras"].items()}


def test_colmap_on_its_own_places_the_scene_and_the_old_photo(tmp_path):
    s = run_colmap(SCENE, IMAGES, tmp_path, query="Img_Old")
    assert s.registered == sorted(IMAGES) and s.missing == []
    assert s.query_registered and s.query_points > 0
    assert s.device == colmap_device()  # the GPU when there is one
    model, cameras = _cameras(tmp_path)
    assert set(model["poses"]) == {*IMAGES, "Img_Old"}  # sfmkit's names, no extension
    assert (tmp_path / "database.db").is_file()
    assert cameras["Img_Old"]["fx"] != cameras["Img01"]["fx"]  # a camera of its own
    # Its principal point is refined, and the view camera's shifted lens puts it
    # well below the centre of the 557 x 418 print.
    assert cameras["Img_Old"]["cy"] > 209 + 50


def test_a_fixed_camera_stays_the_given_k_through_both_passes(tmp_path):
    run_colmap(SCENE, IMAGES, tmp_path, query="Img_Old", K=K)
    _, cameras = _cameras(tmp_path)
    phone = cameras["Img01"]
    # COLMAP's principal point sits half a pixel from OpenCV's.
    assert [phone["fx"], phone["fy"], phone["cx"], phone["cy"]] == pytest.approx(
        [K[0, 0], K[1, 1], K[0, 2] + 0.5, K[1, 2] + 0.5])


def test_colmap_on_sfmkit_matches_uses_them_and_places_the_old_photo(tmp_path):
    matches = [io.load_matches(f) for f in sorted((EXAMPLE / "verify").glob("*.npz"))]
    s = run_colmap_on_matches(SCENE, IMAGES, matches, tmp_path, query="Img_Old")
    assert s.registered == sorted(IMAGES) and s.query_registered
    assert s.device == "cpu"  # no features to extract: mapping alone, which is CPU only
    # Its keypoints are sfmkit's, at most 2048 an image, unlike COLMAP's own SIFT.
    assert max(len(p) for p in _points2d(tmp_path)) <= 2048


def _points2d(out):
    rows = [r for r in (out / "images.txt").read_text().splitlines() if not r.startswith("#")]
    return [r.split()[::3] for r in rows[1::2]]
