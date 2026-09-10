import os
from pathlib import Path

import numpy as np
import pytest

from sfmview.adapters.runs_fs import FsRunStore
from sfmview.domain import RunId, RunNotFound
from synthetic import make_run

EXAMPLES = Path(__file__).resolve().parents[3] / "examples"


def apply(T, X):
    return X @ T[:3, :3].T + T[:3, 3]


def test_runs_are_listed_newest_first_with_what_they_hold(tmp_path):
    make_run(tmp_path, "city", "old", colmap=False, timestamp="2026-01-01T00:00:00+00:00")
    make_run(tmp_path, "city", "new", dense=True, timestamp="2026-02-01T00:00:00+00:00")
    runs = FsRunStore(tmp_path).runs()

    assert [str(r.run) for r in runs] == ["city/new", "city/old"]
    new, old = runs
    assert new.layers == ("sfmkit", "colmap", "dense")
    assert old.layers == ("sfmkit",)
    assert new.stages == ("calibrate", "colmap", "dense", "evaluate", "reconstruct")
    assert new.metrics["mean_rotation_error_deg"] == 0.5
    assert old.metrics == {}


def test_directories_that_are_not_runs_are_skipped(tmp_path):
    make_run(tmp_path, "city", "full")
    (tmp_path / "city" / ".cache" / "x").mkdir(parents=True)
    (tmp_path / "city" / ".cache" / "x" / "manifest.json").write_text("{}")
    (tmp_path / "loose.json").write_text("{}")
    assert [str(r.run) for r in FsRunStore(tmp_path).runs()] == ["city/full"]


def test_the_scene_aligns_sfmkit_onto_colmap(tmp_path):
    make_run(tmp_path, "city", "full", dense=True)
    scene = FsRunStore(tmp_path).scene(RunId("city", "full"))
    ours, theirs = scene.models
    assert (ours.source, theirs.source) == ("sfmkit", "colmap")
    assert scene.reference == "Img02"
    assert np.allclose(apply(ours.to_common, ours.points), apply(theirs.to_common, theirs.points))
    assert scene.dense_to_common is theirs.to_common
    assert ours.cameras[0].size == (640, 480)  # COLMAP's, which records it


def test_a_run_with_colmap_only_is_drawn(tmp_path):
    make_run(tmp_path, "city", "ref", sfmkit=False)
    (only,) = FsRunStore(tmp_path).scene(RunId("city", "ref")).models
    assert only.source == "colmap"


def test_a_run_with_nothing_to_draw_is_not_found(tmp_path):
    make_run(tmp_path, "city", "early", sfmkit=False, colmap=False)
    with pytest.raises(RunNotFound):
        FsRunStore(tmp_path).scene(RunId("city", "early"))


def test_unknown_runs_are_not_found(tmp_path):
    store = FsRunStore(tmp_path)
    with pytest.raises(RunNotFound):
        store.scene(RunId("city", "nope"))
    with pytest.raises(RunNotFound):
        store.dense_file(RunId("city", "nope"))


def test_the_dense_file(tmp_path):
    run = make_run(tmp_path, "city", "full", dense=True)
    store = FsRunStore(tmp_path)
    assert store.dense_file(RunId("city", "full")) == run / "dense" / "fused.ply"
    make_run(tmp_path, "city", "sparse")
    with pytest.raises(RunNotFound):
        store.dense_file(RunId("city", "sparse"))


def test_a_symlink_out_of_the_root_is_not_followed(tmp_path):
    outside = make_run(tmp_path / "elsewhere", "x", "secret", dense=True)
    root = tmp_path / "runs"
    (root / "city").mkdir(parents=True)
    os.symlink(outside, root / "city" / "link")
    store = FsRunStore(root)
    with pytest.raises(RunNotFound):
        store.scene(RunId("city", "link"))
    with pytest.raises(RunNotFound):
        store.dense_file(RunId("city", "link"))


@pytest.mark.skipif(not (EXAMPLES / "valencia" / "9cameras").is_dir(), reason="no example run")
def test_the_valencia_example():
    """The saved run: sfmkit and the course's COLMAP model, the old photo in both."""
    scene = FsRunStore(EXAMPLES).scene(RunId("valencia", "9cameras"))
    ours, theirs = scene.models
    assert scene.reference == "Img02"
    assert len([c for c in ours.cameras if not c.query]) == 9
    assert [c.name for c in ours.cameras if c.query] == ["Img00"]
    assert [c.name for c in theirs.cameras if c.query] == ["Img00"]
    # evaluate scales by Img12's distance from the reference: in the shared frame
    # the two Img12 sit at the same distance, and the rest close by.
    def centre(model, name):
        return apply(model.to_common, model.camera(name).center)

    ours_12, theirs_12 = centre(ours, "Img12"), centre(theirs, "Img12")
    assert np.isclose(np.linalg.norm(ours_12), np.linalg.norm(theirs_12))
    gaps = [np.linalg.norm(centre(ours, c.name) - centre(theirs, c.name))
            for c in ours.cameras if not c.query]
    assert max(gaps) < 0.3
