"""RANSAC: determinism, seeding, and the degenerate cases the original mishandled."""

import numpy as np
import pytest

from sfmkit.core.geometry import sampson_distance
from sfmkit.core.robust import ransac_fundamental, ransac_pnp


class TestRansacFundamental:
    def test_same_seed_gives_identical_results(self, scene):
        m = scene.matches_for("cam00", "cam02", noise=0.5, outlier_ratio=0.3, seed=1)
        x0, x1 = m.points()
        a = ransac_fundamental(x0, x1, seed=42)
        b = ransac_fundamental(x0, x1, seed=42)
        assert np.array_equal(a.inliers, b.inliers)
        assert np.allclose(a.model, b.model)

    def test_different_seeds_may_differ_but_both_succeed(self, scene):
        """Documents the variance the original had, uncontrolled, in production."""
        m = scene.matches_for("cam00", "cam02", noise=0.5, outlier_ratio=0.3, seed=1)
        x0, x1 = m.points()
        results = [ransac_fundamental(x0, x1, seed=s) for s in range(5)]
        assert all(r.converged for r in results)
        counts = [r.n_inliers for r in results]
        assert max(counts) - min(counts) < 0.2 * max(counts), "seed choice should not dominate"

    def test_rejects_outliers(self, scene):
        m = scene.matches_for("cam00", "cam02", noise=0.3, outlier_ratio=0.4, seed=2)
        x0, x1 = m.points()
        res = ransac_fundamental(x0, x1, threshold=2.0, seed=0)
        assert res.converged
        # Roughly the planted inlier fraction, and the survivors must actually fit.
        assert 0.45 < res.n_inliers / len(x0) < 0.85
        assert sampson_distance(res.model, x0[res.inliers], x1[res.inliers]).mean() < 2.0

    def test_too_few_points_returns_cleanly(self, rng):
        """The original raised UnboundLocalError instead of reporting failure."""
        res = ransac_fundamental(rng.normal(size=(5, 2)), rng.normal(size=(5, 2)), seed=0)
        assert res.model is None
        assert not res.converged
        assert res.n_inliers == 0

    def test_pure_noise_does_not_crash(self, rng):
        x0 = rng.uniform(0, 1000, size=(60, 2))
        x1 = rng.uniform(0, 1000, size=(60, 2))
        res = ransac_fundamental(x0, x1, threshold=0.5, seed=0)
        assert res.inliers.shape == (60,)

    def test_stops_early_on_clean_data(self, scene):
        """Adaptive termination: a clean pair must not burn all 1000 trials."""
        m = scene.matches_for("cam00", "cam01")
        x0, x1 = m.points()
        res = ransac_fundamental(x0, x1, max_iterations=1000, seed=0)
        assert res.converged
        assert res.n_iterations < 200


class TestRansacPnp:
    def test_recovers_a_known_pose(self, scene):
        pytest.importorskip("cv2")
        name = "cam03"
        idx = scene.visible[name]
        res = ransac_pnp(scene.points[idx], scene.keypoints[name], scene.K, seed=0)
        assert res.converged
        from sfmkit.core.metrics import rotation_error_deg
        truth = scene.poses[name]
        assert rotation_error_deg(res.model.R, truth.R) < 0.5
        assert np.linalg.norm(res.model.t - truth.t) < 0.05

    def test_is_deterministic_under_a_fixed_seed(self, scene):
        pytest.importorskip("cv2")
        name = "cam03"
        idx = scene.visible[name]
        a = ransac_pnp(scene.points[idx], scene.keypoints[name], scene.K, seed=7)
        b = ransac_pnp(scene.points[idx], scene.keypoints[name], scene.K, seed=7)
        assert np.allclose(a.model.R, b.model.R)
        assert np.allclose(a.model.t, b.model.t)

    def test_too_few_correspondences(self, scene):
        res = ransac_pnp(scene.points[:3], scene.keypoints["cam00"][:3], scene.K, seed=0)
        assert res.model is None
        assert not res.converged
