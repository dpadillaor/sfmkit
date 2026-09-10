"""Run manifests: where they land and what they record."""

import pytest

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


class TestImageFile:
    """Images are named without extension; image_file finds the file."""

    def test_finds_the_file_whatever_its_extension(self, tmp_path):
        (tmp_path / "Img12.jpg").write_bytes(b"")
        (tmp_path / "Img00").write_bytes(b"")
        assert io.image_file(tmp_path, "Img12") == tmp_path / "Img12.jpg"
        assert io.image_file(tmp_path, "Img00") == tmp_path / "Img00"

    def test_a_name_is_not_a_prefix(self, tmp_path):
        (tmp_path / "Img12.jpg").write_bytes(b"")
        with pytest.raises(FileNotFoundError, match="Img1"):
            io.image_file(tmp_path, "Img1")

    def test_two_candidate_files_is_an_error(self, tmp_path):
        (tmp_path / "Img02.jpg").write_bytes(b"")
        (tmp_path / "Img02.png").write_bytes(b"")
        with pytest.raises(ValueError, match="ambiguous"):
            io.image_file(tmp_path, "Img02")
