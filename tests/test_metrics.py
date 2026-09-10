"""Scoring one reconstruction against another."""

import numpy as np
import pytest

from sfmkit.core.metrics import compare_camera, compare_poses, rotation_error_deg
from sfmkit.core.types import Pose


def _rot(axis, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    return {"x": np.array([[1, 0, 0], [0, c, -s], [0, s, c]]),
            "y": np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])}[axis]


@pytest.fixture
def truth():
    return {
        "ref": Pose(np.eye(3), np.zeros(3)),
        "far": Pose(_rot("y", 10), np.array([-2.0, 0.0, 0.5])),
        "near": Pose(_rot("y", -5), np.array([0.5, 0.1, 0.0])),
        "query": Pose(_rot("x", 3), np.array([0.2, 0.0, 0.1])),
    }


def _regauged(poses, scale):
    """The same cameras in another world frame, and at another scale."""
    g = Pose(_rot("y", 30) @ _rot("x", 20), np.array([5.0, -1.0, 2.0]))
    return {n: Pose(p.R @ g.R.T, scale * (p.t - p.R @ g.R.T @ g.t)) for n, p in poses.items()}


def test_a_camera_is_scored_as_compare_poses_scores_it(truth):
    estimate = _regauged(truth, scale=3.0)
    estimate["query"] = Pose(_rot("x", 2) @ estimate["query"].R, estimate["query"].t)
    cmp = compare_poses({n: p for n, p in estimate.items() if n != "query"}, truth, "ref")
    row = compare_camera(estimate, truth, "query", cmp["reference"], cmp["scale_image"])
    assert row["rotation_error_deg"] == pytest.approx(2.0, abs=1e-6)
    assert cmp["mean_rotation_error_deg"] == pytest.approx(0.0, abs=1e-6)  # query kept out


def test_the_gauge_and_scale_do_not_count_as_error(truth):
    cmp = compare_poses(_regauged(truth, scale=0.5), truth, "ref")
    assert cmp["max_rotation_error_deg"] == pytest.approx(0.0, abs=1e-6)
    assert all(r["position_error"] < 1e-9 for r in cmp["cameras"])
    assert rotation_error_deg(np.eye(3), _rot("y", 7)) == pytest.approx(7.0)
