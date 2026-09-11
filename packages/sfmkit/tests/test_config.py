"""Config loading: sections, the data root, and where a run is written."""

from pathlib import Path

import pytest

from sfmkit.data.config import default_run_dir, load_config

REPO = Path(__file__).resolve().parents[3]


def _write(dirpath: Path, body: str, name: str = "exp.yaml") -> Path:
    dirpath.mkdir(parents=True, exist_ok=True)
    cfg = dirpath / name
    cfg.write_text(body)
    return cfg


def test_paths_resolve_against_the_dataset_under_the_data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("SFMKIT_DATA", str(tmp_path / "mnt"))
    cfg = _write(tmp_path / "configs", (
        "dataset: city\n"
        "calibrate: {intrinsics: precomputed/K.txt}\n"
        "colmap: {precomputed: precomputed/colmap}\n"
    ))
    monkeypatch.chdir(tmp_path)  # run from an unrelated directory
    c = load_config(cfg)
    dataset = tmp_path / "mnt" / "city"
    assert c.scene_dir == dataset / "scene"
    assert Path(c.calibrate.intrinsics) == dataset / "precomputed" / "K.txt"
    assert Path(c.colmap.precomputed) == dataset / "precomputed" / "colmap"


def test_absolute_paths_are_left_alone(tmp_path):
    cfg = _write(tmp_path, "dataset: city\ncolmap: {precomputed: /models/city}\n")
    assert load_config(cfg).colmap.precomputed == "/models/city"


def test_empty_paths_stay_empty(tmp_path):
    """An absent COLMAP model must not become the dataset directory."""
    cfg = _write(tmp_path, "dataset: city\n")
    c = load_config(cfg)
    assert c.colmap.precomputed == "" and c.calibrate.intrinsics == ""


def test_dataset_is_required(tmp_path):
    cfg = _write(tmp_path, "sfm: {images: [a, b]}\n")
    with pytest.raises(ValueError, match="dataset"):
        load_config(cfg)


def test_unknown_keys_are_rejected_at_the_top_and_in_sections(tmp_path):
    with pytest.raises(ValueError, match="sfn"):
        load_config(_write(tmp_path, "dataset: city\nsfn: {}\n"))
    with pytest.raises(ValueError, match="imags"):
        load_config(_write(tmp_path, "dataset: city\nsfm: {imags: [a]}\n"))


def test_the_device_defaults_to_auto_and_is_checked(tmp_path):
    assert load_config(_write(tmp_path, "dataset: city\n")).sfm.device == "auto"
    with pytest.raises(ValueError, match="device"):
        load_config(_write(tmp_path, "dataset: city\nsfm: {device: gpu}\n"))


def test_colmap_is_either_precomputed_or_computed_never_both(tmp_path):
    with pytest.raises(ValueError, match="not both"):
        load_config(_write(tmp_path, "dataset: city\ncolmap: {precomputed: m, matches: colmap}\n"))
    with pytest.raises(ValueError, match="matches"):
        load_config(_write(tmp_path, "dataset: city\ncolmap: {matches: sift}\n"))
    for who in ("colmap", "sfmkit"):
        c = load_config(_write(tmp_path, f"dataset: city\ncolmap: {{matches: {who}}}\n"))
        assert c.colmap.matches == who


def test_the_colmap_camera_is_checked(tmp_path):
    assert load_config(_write(tmp_path, "dataset: city\n")).colmap.camera == "self"
    with pytest.raises(ValueError, match="camera"):
        load_config(_write(tmp_path, "dataset: city\ncolmap: {matches: colmap, camera: k}\n"))
    with pytest.raises(ValueError, match="precomputed"):
        load_config(_write(tmp_path, "dataset: city\ncolmap: {precomputed: m, camera: fixed}\n"))


def test_the_dense_map_is_off_unless_asked_for(tmp_path):
    c = load_config(_write(tmp_path, "dataset: city\n"))
    assert c.dense.enabled is False and c.dense.max_image_size == 2000
    with pytest.raises(ValueError, match="max_image_size"):
        load_config(_write(tmp_path, "dataset: city\ndense: {enabled: true, max_image_size: 0}\n"))


def test_the_run_is_named_after_the_dataset_and_the_config(tmp_path, monkeypatch):
    monkeypatch.setenv("SFMKIT_RUNS", str(tmp_path / "out"))
    c = load_config(_write(tmp_path, "dataset: city\n", name="night.yaml"))
    assert c.name == "night"
    assert default_run_dir(c) == tmp_path / "out" / "city" / "night"


def test_the_shipped_configs_point_at_real_files(monkeypatch):
    """Every config in configs/ must resolve to data that exists."""
    monkeypatch.chdir(REPO)
    configs = sorted((REPO / "configs").glob("*/*.yaml"))
    assert configs, "no configs found"
    for cfg in configs:
        c = load_config(cfg)
        assert c.dataset == cfg.parent.name, f"{cfg}: lives under the wrong dataset"
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


def test_the_exif_config_loads():
    cfg = load_config(REPO / "configs" / "valencia" / "9cameras-exif.yaml")
    assert cfg.calibrate.exif and cfg.dense.enabled and not cfg.calibrate.intrinsics
