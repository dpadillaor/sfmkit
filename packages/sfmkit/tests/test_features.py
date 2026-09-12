"""Choosing the device for matching, without needing PyTorch or a GPU."""

import pytest

from sfmkit.data.features import resolve_device


@pytest.mark.parametrize(("requested", "gpu", "expected"), [
    ("auto", True, "cuda"),
    ("auto", False, "cpu"),
    ("cpu", True, "cpu"),
    ("cuda", True, "cuda"),
])
def test_resolves_to_a_real_device(requested, gpu, expected):
    assert resolve_device(requested, cuda_available=gpu) == expected


def test_asking_for_a_gpu_that_is_not_there_is_an_error():
    """Falling back to the CPU silently would change the matches, and the result."""
    with pytest.raises(ValueError, match="no GPU"):
        resolve_device("cuda", cuda_available=False)


def test_unknown_devices_are_rejected():
    with pytest.raises(ValueError, match="device"):
        resolve_device("tpu", cuda_available=True)


class TestWeights:
    """They are downloaded, not shipped: sfmkit may not pass Magic Leap's on."""

    def test_where_they_go_follows_torch(self, tmp_path, monkeypatch):
        from sfmkit.data import features

        monkeypatch.setenv("TORCH_HOME", str(tmp_path / "torch"))
        assert features.weights_dir() == tmp_path / "torch" / "hub" / "checkpoints"
        monkeypatch.delenv("TORCH_HOME")
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
        assert features.weights_dir() == tmp_path / "cache" / "torch" / "hub" / "checkpoints"

    def test_missing_names_the_ones_not_there(self, tmp_path, monkeypatch):
        from sfmkit.data import features

        monkeypatch.setenv("TORCH_HOME", str(tmp_path))
        assert features.missing_weights() == list(features.WEIGHTS)
        where = tmp_path / "hub" / "checkpoints"
        where.mkdir(parents=True)
        (where / "superpoint_v1.pth").write_bytes(b"not really weights")
        assert features.missing_weights() == ["superpoint_lightglue_v0-1_arxiv.pth"]

    def test_the_help_speaks_of_compose_inside_a_container(self, monkeypatch):
        from sfmkit.data import features

        monkeypatch.setattr(features, "in_container", lambda: True)
        inside = features.weights_help()
        assert "SFMKIT_WEIGHTS" in inside and "docker run" in inside
        monkeypatch.setattr(features, "in_container", lambda: False)
        outside = features.weights_help()
        assert "TORCH_HOME" in outside and "SFMKIT_WEIGHTS" not in outside
        for text in (inside, outside):
            assert all(url in text for url in features.WEIGHTS.values())
            assert "noncommercial" in text
