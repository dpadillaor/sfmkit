"""The figures that carry an argument, checked where the argument could break.

A PNG cannot be asserted on, so these render the awkward cases rather than the
happy one: an epipole with no pixel to sit at, and a pose whose triangulation
does not resolve.
"""

import numpy as np
import pytest

from sfmkit.core.geometry import eight_point, epipoles, fundamental_to_essential


@pytest.fixture
def pair(scene):
    m = scene.matches_for("cam00", "cam02")
    return m.points()


def test_the_epipolar_figure_survives_an_epipole_at_infinity(scene, pair, tmp_path):
    """The synthetic cameras face one wall, so neither epipole has a pixel, and
    dividing by its third coordinate would put a marker anywhere at all."""
    from sfmkit.render.viz import plot_epipolar

    x0, x1 = pair
    assert abs(epipoles(eight_point(x0, x1))[0][2]) < 1e-3, "the awkward case, still awkward"
    blank = np.zeros((1200, 1600, 3), dtype=np.uint8)
    out = plot_epipolar(blank, blank, eight_point(x0, x1), x0, tmp_path / "epipolar.png")
    assert out.is_file() and out.stat().st_size > 1000


def test_the_pose_candidates_figure_draws_all_four(scene, pair, tmp_path):
    from sfmkit.render.viz import plot_pose_candidates

    x0, x1 = pair
    E = fundamental_to_essential(eight_point(x0, x1), scene.K, scene.K)
    out = plot_pose_candidates(E, scene.K, x0, x1, tmp_path / "poses.png")
    assert out.is_file() and out.stat().st_size > 1000


def test_the_pose_candidates_figure_survives_a_degenerate_pair(scene, tmp_path):
    """Eight points on a plane at one depth: the box it sizes itself from can
    come out empty, and an empty box is a division by zero waiting."""
    from sfmkit.render.viz import plot_pose_candidates

    x0 = np.array([[100.0, 100], [200, 100], [300, 100], [400, 100],
                   [100, 200], [200, 200], [300, 200], [400, 200]])
    E = fundamental_to_essential(eight_point(x0, x0 + 5.0), scene.K, scene.K)
    out = plot_pose_candidates(E, scene.K, x0, x0 + 5.0, tmp_path / "degenerate.png")
    assert out.is_file()
