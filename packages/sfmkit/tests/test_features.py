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
