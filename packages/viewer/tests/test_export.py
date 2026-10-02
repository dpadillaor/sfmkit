import json

import pytest
from PIL import Image

from sfmcontracts import STEP_EXAMPLES
from sfmview.export import ORIENTATION, export
from synthetic import NAMES, make_run

MAKE, DATE = 0x010F, 0x0132


def photo(path, size=(4000, 3000), orientation=6):
    """A photo as a phone leaves it: turned by its EXIF, and saying what took it when."""
    exif = Image.Exif()
    exif[ORIENTATION] = orientation
    exif[MAKE] = "a phone"
    exif[DATE] = "2026:09:01 12:00:00"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (90, 120, 150)).save(path, exif=exif.tobytes())


@pytest.fixture
def projects(tmp_path):
    root = tmp_path / "projects"
    make_run(root, "city", "full", dense=True)
    make_run(root, "city", "sparse")
    for name in NAMES:
        photo(root / "city" / "data" / "scene" / f"{name}.jpg")
    steps = tmp_path / "steps" / "city"
    steps.mkdir(parents=True)
    (steps / "full.json").write_text(json.dumps(STEP_EXAMPLES))
    return root


def test_the_copy_names_where_its_answers_are(projects, tmp_path):
    out = tmp_path / "demo"
    export(projects, out)
    page = (out / "index.html").read_text()
    assert '<meta name="sfmview-data" content="data/">' in page
    assert (out / "js" / "main.js").is_file() and (out / "vendor" / "three").is_dir()


def test_every_url_in_the_copy_is_relative_and_there(projects, tmp_path):
    out = tmp_path / "demo"
    export(projects, out, steps=tmp_path / "steps")
    runs = json.loads((out / "data" / "runs.json").read_text())
    assert {r["id"] for r in runs} == {"city/full", "city/sparse"}
    assert all(r["running"] is False for r in runs)  # nothing is at work on a copy
    scene = json.loads((out / "data" / "runs" / "city" / "full" / "scene.json").read_text())
    assert not scene["dense"]["url"].startswith("/")
    assert (out / scene["dense"]["url"]).is_file()
    assert scene["images"] == "data/images/city"
    for name in NAMES:
        assert (out / scene["images"] / f"{name}.jpg").is_file()


def test_a_recorded_stream_is_replayed_as_the_socket_sends_it(projects, tmp_path):
    out = tmp_path / "demo"
    export(projects, out, steps=tmp_path / "steps")
    stream = json.loads((out / "data" / "runs" / "city" / "full" / "steps.json").read_text())
    assert [e["message"] for e in stream] == STEP_EXAMPLES
    assert [e["id"] for e in stream] == [f"{i}-0" for i in range(1, len(STEP_EXAMPLES) + 1)]
    assert not (out / "data" / "runs" / "city" / "sparse" / "steps.json").exists()


def test_a_stream_that_breaks_the_contract_is_refused(projects, tmp_path):
    (tmp_path / "steps" / "city" / "full.json").write_text(json.dumps([{"kind": "step"}]))
    with pytest.raises(SystemExit, match="message 0"):
        export(projects, tmp_path / "demo", steps=tmp_path / "steps")


def test_photos_are_smaller_and_keep_only_their_orientation(projects, tmp_path):
    out = tmp_path / "demo"
    export(projects, out, photo_size=1000, quality=85)
    with Image.open(out / "data" / "images" / "city" / f"{NAMES[0]}.jpg") as im:
        assert im.size == (1000, 750)  # as stored, not turned: the page turns it
        assert dict(im.getexif()) == {ORIENTATION: 6}


def test_only_the_runs_asked_for(projects, tmp_path):
    out = tmp_path / "demo"
    export(projects, out, runs=["city/sparse"])
    runs = json.loads((out / "data" / "runs.json").read_text())
    assert [r["id"] for r in runs] == ["city/sparse"]
    with pytest.raises(SystemExit, match="no such run"):
        export(projects, out, runs=["city/missing"])


def test_an_old_copy_is_replaced_but_nothing_else(projects, tmp_path):
    out = tmp_path / "demo"
    export(projects, out)
    (out / "stale.txt").write_text("from the last copy")
    export(projects, out)
    assert not (out / "stale.txt").exists()

    other = tmp_path / "other"
    other.mkdir()
    (other / "notes.txt").write_text("mine")
    with pytest.raises(SystemExit, match="not a copy"):
        export(projects, other)
    assert (other / "notes.txt").read_text() == "mine"
