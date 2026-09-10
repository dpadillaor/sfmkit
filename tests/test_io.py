"""Run manifests: where they land and what they record."""

from sfmkit.data import io


def test_a_manifest_lands_in_its_stage_folder(tmp_path):
    path = io.write_manifest(tmp_path, "verify", {"dataset": "x"})
    assert path == tmp_path / "verify" / "manifest.json"
    assert io.read_manifest(tmp_path, "verify")["stage"] == "verify"


def test_the_commit_can_come_from_the_environment(tmp_path, monkeypatch):
    """Inside an image there is no .git; the build passes the commit instead."""
    monkeypatch.setenv("SFMKIT_GIT_COMMIT", "abc123")
    io.write_manifest(tmp_path, "match", {})
    assert io.read_manifest(tmp_path, "match")["git_commit"] == "abc123"


def test_paths_under_the_working_directory_are_recorded_relative(tmp_path, monkeypatch):
    """So an example run carries no one's home directory, and reads the same in the image."""
    root = tmp_path.resolve()  # as load_config resolves the dataset directory
    monkeypatch.chdir(root)
    config = {"dataset_dir": str(root / "data" / "city"), "model": "/elsewhere/colmap",
              "images": ["Img00"]}
    io.write_manifest(root, "colmap", config, config_path=str(root / "c.yaml"))
    m = io.read_manifest(root, "colmap")
    assert m["config"]["dataset_dir"] == "data/city"
    assert m["config"]["model"] == "/elsewhere/colmap"
    assert m["config"]["images"] == ["Img00"]
    assert m["config_path"] == "c.yaml"
