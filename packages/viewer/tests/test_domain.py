import numpy as np
import pytest

from sfmview.domain import Camera, RunId


@pytest.mark.parametrize("name", ["valencia", "9cameras-dense", "run_2.b"])
def test_run_names_are_single_path_components(name):
    assert str(RunId("p", name)) == f"p/{name}"


@pytest.mark.parametrize("name", ["", ".", "..", "../etc", "a/b", "a\\b", ".hidden", "a b"])
def test_other_names_are_refused(name):
    with pytest.raises(ValueError):
        RunId("valencia", name)
    with pytest.raises(ValueError):
        RunId(name, "9cameras")


def test_a_camera_centre_is_minus_r_transpose_t():
    R = np.array([[0.0, -1, 0], [1, 0, 0], [0, 0, 1]])
    centre = np.array([1.0, 2, 3])
    assert np.allclose(Camera("a", R, -R @ centre).center, centre)
