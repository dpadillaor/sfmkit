"""`sfmkit new`: what it lays out is what the rest of the tools expect.

The template is a piece of text until something parses it. Here it is loaded
as a config, and the stages `run` would do on it are the ones it configures --
so a template that drifts from the config module fails here rather than in a
newcomer's first minute.
"""

import pytest

from sfmkit.apps.cli.new import cmd_new
from sfmkit.apps.cli.run import STAGES, configured
from sfmkit.data.config import load_config, project_dir


class _Args:
    def __init__(self, name, inside, photos=None):
        self.name = name
        self.inside = str(inside)
        self.photos = None if photos is None else str(photos)


@pytest.fixture
def photographs(tmp_path):
    source = tmp_path / "photographs"
    source.mkdir()
    for name in ("Img02.jpg", "Img01.jpg", "notes.txt"):
        (source / name).write_bytes(b"")
    return source


def _project(tmp_path, **kw):
    assert cmd_new(_Args("city", tmp_path, **kw)) == 0
    return tmp_path / "city", tmp_path / "city" / "configs" / "cpu.yaml"


def test_the_layout_is_the_one_a_config_is_found_by(tmp_path):
    project, config = _project(tmp_path)
    assert (project / "data" / "scene").is_dir()
    assert project_dir(config) == project


def test_the_template_is_a_config(tmp_path):
    _, config = _project(tmp_path)
    cfg = load_config(config)
    assert cfg.dataset == "city"
    assert cfg.name == "cpu"
    assert cfg.calibrate.exif
    assert cfg.sfm.images == []


def test_photographs_are_copied_and_listed_in_order(tmp_path, photographs):
    project, config = _project(tmp_path, photos=photographs)
    assert load_config(config).sfm.images == ["Img01", "Img02"]
    assert sorted(p.name for p in (project / "data" / "scene").iterdir()) == \
        ["Img01.jpg", "Img02.jpg"]


def test_a_long_list_of_photographs_stays_readable(tmp_path):
    source = tmp_path / "photographs"
    source.mkdir()
    for i in range(30):
        (source / f"Img{i:02d}.jpg").write_bytes(b"")
    _, config = _project(tmp_path, photos=source)
    assert max(len(line) for line in config.read_text().splitlines()) <= 100
    assert len(load_config(config).sfm.images) == 30


def test_it_refuses_to_write_over_a_project(tmp_path):
    _project(tmp_path)
    assert cmd_new(_Args("city", tmp_path)) == 1


def test_a_directory_with_no_photographs_leaves_nothing_behind(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert cmd_new(_Args("city", tmp_path, photos=empty)) == 1
    assert not (tmp_path / "city").exists(), "a failure must not leave half a project"


def test_two_photographs_of_the_same_name_are_refused(tmp_path):
    source = tmp_path / "photographs"
    source.mkdir()
    (source / "Img01.jpg").write_bytes(b"")
    (source / "Img01.png").write_bytes(b"")
    assert cmd_new(_Args("city", tmp_path, photos=source)) == 1


def test_a_new_project_runs_the_stages_it_has(tmp_path, photographs):
    """No historical photograph and no COLMAP: those stages are walked past,
    and what is left is a reconstruction and its figures."""
    _, config = _project(tmp_path, photos=photographs)
    cfg = load_config(config)
    wanted = [name for name, _ in STAGES if configured(cfg, name)]
    assert wanted == ["calibrate", "match", "verify", "reconstruct", "dense", "figures"]
