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
