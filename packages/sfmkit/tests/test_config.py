"""Config loading: sections, the project it sits in, and where a run is written."""

from pathlib import Path

import pytest

from sfmkit.data.config import default_run_dir, load_config, project_dir

REPO = Path(__file__).resolve().parents[3]


def _write(root: Path, body: str, name: str = "exp.yaml", project: str = "city") -> Path:
    """A config where one belongs: ``<root>/<project>/configs/<name>``."""
    configs = root / project / "configs"
    configs.mkdir(parents=True, exist_ok=True)
    cfg = configs / name
    cfg.write_text(body)
    return cfg


def test_paths_resolve_against_the_project_the_config_sits_in(tmp_path, monkeypatch):
    cfg = _write(tmp_path, (
        "calibrate: {intrinsics: precomputed/K.txt}\n"
        "colmap: {precomputed: precomputed/colmap}\n"
    ))
    monkeypatch.chdir(tmp_path)  # run from an unrelated directory
    c = load_config(cfg)
    dataset = tmp_path / "city" / "data"
    assert c.scene_dir == dataset / "scene"
    assert Path(c.calibrate.intrinsics) == dataset / "precomputed" / "K.txt"
    assert Path(c.colmap.precomputed) == dataset / "precomputed" / "colmap"


def test_absolute_paths_are_left_alone(tmp_path):
    cfg = _write(tmp_path, "colmap: {precomputed: /models/city}\n")
    assert load_config(cfg).colmap.precomputed == "/models/city"


def test_empty_paths_stay_empty(tmp_path):
    """An absent COLMAP model must not become the dataset directory."""
    cfg = _write(tmp_path, "seed: 0\n")
    c = load_config(cfg)
    assert c.colmap.precomputed == "" and c.calibrate.intrinsics == ""


def test_the_project_is_where_the_config_sits(tmp_path):
    cfg = _write(tmp_path, "sfm: {images: [a, b]}\n", project="harbour")
    c = load_config(cfg)
    assert c.dataset == "harbour"
    assert project_dir(cfg) == tmp_path / "harbour"


def test_a_config_outside_a_configs_directory_is_refused(tmp_path):
    stray = tmp_path / "exp.yaml"
    stray.write_text("seed: 0\n")
    with pytest.raises(ValueError, match="configs"):
        load_config(stray)


def test_the_dataset_key_is_gone(tmp_path):
    """It named the project a second time, and nothing checked the two agreed."""
    with pytest.raises(ValueError, match="dataset"):
        load_config(_write(tmp_path, "dataset: city\n"))


def test_unknown_keys_are_rejected_at_the_top_and_in_sections(tmp_path):
    with pytest.raises(ValueError, match="sfn"):
        load_config(_write(tmp_path, "sfn: {}\n"))
    with pytest.raises(ValueError, match="imags"):
        load_config(_write(tmp_path, "sfm: {imags: [a]}\n"))


def test_the_device_defaults_to_auto_and_is_checked(tmp_path):
    assert load_config(_write(tmp_path, "seed: 0\n")).sfm.device == "auto"
    with pytest.raises(ValueError, match="device"):
        load_config(_write(tmp_path, "sfm: {device: gpu}\n"))


def test_colmap_is_either_precomputed_or_computed_never_both(tmp_path):
    with pytest.raises(ValueError, match="not both"):
        load_config(_write(tmp_path, "colmap: {precomputed: m, matches: colmap}\n"))
    with pytest.raises(ValueError, match="matches"):
        load_config(_write(tmp_path, "colmap: {matches: sift}\n"))
    for who in ("colmap", "sfmkit"):
        c = load_config(_write(tmp_path, f"colmap: {{matches: {who}}}\n"))
        assert c.colmap.matches == who


def test_the_colmap_camera_is_checked(tmp_path):
    assert load_config(_write(tmp_path, "seed: 0\n")).colmap.camera == "self"
    with pytest.raises(ValueError, match="camera"):
        load_config(_write(tmp_path, "colmap: {matches: colmap, camera: k}\n"))
    with pytest.raises(ValueError, match="precomputed"):
        load_config(_write(tmp_path, "colmap: {precomputed: m, camera: fixed}\n"))


def test_the_dense_map_is_off_unless_asked_for(tmp_path):
    c = load_config(_write(tmp_path, "seed: 0\n"))
    assert c.dense.enabled is False and c.dense.max_image_size == 2000
    with pytest.raises(ValueError, match="max_image_size"):
        load_config(_write(tmp_path, "dense: {enabled: true, max_image_size: 0}\n"))


def test_a_run_is_written_inside_its_project(tmp_path):
    c = load_config(_write(tmp_path, "seed: 0\n", name="night.yaml"))
    assert c.name == "night"
    assert default_run_dir(c) == tmp_path / "city" / "runs" / "night"


def test_the_shipped_configs_point_at_real_files(monkeypatch):
    """Every config shipped must resolve to data that exists."""
    monkeypatch.chdir(REPO)
    configs = sorted((REPO / "projects").glob("*/configs/*.yaml"))
    assert configs, "no configs found"
    for cfg in configs:
        c = load_config(cfg)
        assert c.dataset == cfg.parents[1].name, f"{cfg}: lives under the wrong project"
        for name in [*c.sfm.images, c.localize.query]:
            assert list(c.scene_dir.glob(f"{name}.*")), f"{cfg}: no photo named {name}"
        if c.calibrate.intrinsics:
            assert Path(c.calibrate.intrinsics).is_file(), f"{cfg}: {c.calibrate.intrinsics}"
        if c.colmap.precomputed:
            model = Path(c.colmap.precomputed)
            assert (model / "images.txt").is_file(), f"{cfg}: {model}"


def test_calibrate_takes_one_source():
    from sfmkit.data.config import CalibrateConfig

    assert CalibrateConfig(exif=True).exif
    with pytest.raises(ValueError, match="one source"):
        CalibrateConfig(intrinsics="K.txt", exif=True)
    with pytest.raises(ValueError, match="sensor_aspect"):
        CalibrateConfig(exif=True, sensor_aspect=[4])


def test_the_valencia_configs_take_k_from_exif():
    for config in (REPO / "projects" / "valencia" / "configs").glob("*.yaml"):
        assert load_config(config).calibrate.exif, config.stem


def test_the_schur_solver_is_the_default():
    from sfmkit.data.config import SfmConfig

    assert SfmConfig().bundle_solver == "schur"
    with pytest.raises(ValueError, match="bundle_solver"):
        SfmConfig(bundle_solver="ceres")
