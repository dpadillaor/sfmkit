"""Bundle adjustment: correctness, sparsity structure, and gauge handling."""

import numpy as np
import pytest

from sfmkit.core.bundle import BundleProblem, solve_bundle
from sfmkit.core.bundle_schur import solve_bundle_schur
from sfmkit.core.types import Pose


def _problem_from_scene(scene, n_cameras=3):
    """Ground-truth poses/points plus every observation, in bundle input form."""
    images = scene.images[:n_cameras]
    ref = images[0]
    poses = {n: scene.poses[n].relative_to(scene.poses[ref]) for n in images}
    # Gauge: reference at the identity, unit baseline on the second camera. The
    # points must move into the reference frame too, not merely be rescaled.
    s = np.linalg.norm(poses[images[1]].t)
    poses = {n: Pose(p.R, p.t / s) for n, p in poses.items()}
    points = scene.poses[ref].transform(scene.points) / s

    rows = []
    for ci, img in enumerate(images):
        for k, pid in enumerate(scene.visible[img]):
            rows.append((int(pid), ci, *scene.keypoints[img][k]))
    obs = np.asarray(rows, dtype=float)
    return images, poses, points, obs


class TestPacking:
    def test_pack_unpack_round_trip(self, scene):
        images, poses, points, obs = _problem_from_scene(scene)
        prob = BundleProblem(scene.K, images, poses, points, obs)
        p2, X2 = prob.unpack(prob.pack(poses, points))
        for n in images:
            assert np.allclose(p2[n].R, poses[n].R, atol=1e-9)
            assert np.allclose(p2[n].t, poses[n].t, atol=1e-9)
        assert np.allclose(X2, points, atol=1e-9)

    def test_reference_stays_at_the_identity(self, scene):
        images, poses, points, obs = _problem_from_scene(scene)
        prob = BundleProblem(scene.K, images, poses, points, obs)
        p2, _ = prob.unpack(prob.pack(poses, points) + 0.1)
        assert np.allclose(p2[images[0]].R, np.eye(3))
        assert np.allclose(p2[images[0]].t, np.zeros(3))

    def test_second_baseline_stays_unit_length(self, scene):
        images, poses, points, obs = _problem_from_scene(scene)
        prob = BundleProblem(scene.K, images, poses, points, obs)
        rng = np.random.default_rng(0)
        n_params = prob.point_offset + 3 * len(points)
        p2, _ = prob.unpack(prob.pack(poses, points) + rng.normal(0, 0.3, n_params))
        assert np.isclose(np.linalg.norm(p2[images[1]].t), 1.0)


class TestResidual:
    def test_zero_at_ground_truth(self, scene):
        images, poses, points, obs = _problem_from_scene(scene)
        prob = BundleProblem(scene.K, images, poses, points, obs)
        assert np.abs(prob.residual(prob.pack(poses, points))).max() < 1e-6

    def test_grows_when_a_camera_is_perturbed(self, scene):
        images, poses, points, obs = _problem_from_scene(scene)
        prob = BundleProblem(scene.K, images, poses, points, obs)
        x = prob.pack(poses, points)
        clean = np.abs(prob.residual(x)).mean()
        x[5:8] += 0.05
        assert np.abs(prob.residual(x)).mean() > clean


class TestSparsity:
    def test_shape_and_density(self, scene):
        images, poses, points, obs = _problem_from_scene(scene)
        prob = BundleProblem(scene.K, images, poses, points, obs)
        S = prob.sparsity()
        assert S.shape == (prob.n_residuals, prob.point_offset + 3 * prob.n_points)
        density = S.nnz / (S.shape[0] * S.shape[1])
        assert density < 0.05, "a bundle Jacobian should be overwhelmingly zero"

    def test_pattern_covers_the_true_nonzeros(self, scene):
        """A sparsity pattern that misses a real dependency silently breaks the solve."""
        from scipy.optimize._numdiff import approx_derivative

        images, poses, points, obs = _problem_from_scene(scene, n_cameras=3)
        prob = BundleProblem(scene.K, images, poses, points, obs)
        x = prob.pack(poses, points)
        rng = np.random.default_rng(0)
        x = x + rng.normal(0, 0.01, x.shape)

        J = approx_derivative(prob.residual, x)
        S = prob.sparsity().toarray().astype(bool)
        missed = (np.abs(J) > 1e-6) & ~S
        assert missed.sum() == 0, f"{missed.sum()} true nonzeros outside the declared pattern"


@pytest.fixture(params=[solve_bundle, solve_bundle_schur], ids=["scipy", "schur"])
def solver(request):
    """Either solver: both must pass every test of the solve."""
    return request.param


class TestSolve:
    def test_recovers_perturbed_ground_truth(self, scene, solver):
        """Perturb the truth, optimise, and check it comes back.

        Uses a plain least-squares loss: this tests convergence, not robustness.
        With a Huber loss every residual here is beyond ``f_scale`` and gets
        down-weighted, which is correct behaviour but a different property --
        see ``test_robust_loss_resists_outliers``.
        """
        images, poses, points, obs = _problem_from_scene(scene, n_cameras=4)
        rng = np.random.default_rng(0)
        noisy_points = points + rng.normal(0, 0.05, points.shape)

        res = solver(scene.K, images, poses, noisy_points, obs, loss="linear")
        assert res.rmse_after < res.rmse_before
        assert res.rmse_after < 0.5
        from sfmkit.core.metrics import rotation_error_deg
        for n in images:
            assert rotation_error_deg(res.poses[n].R, poses[n].R) < 1.0

    def test_robust_loss_resists_outliers(self, scene, solver):
        """A few grossly wrong observations must not drag the solution."""
        images, poses, points, obs = _problem_from_scene(scene, n_cameras=4)
        rng = np.random.default_rng(0)
        corrupted = obs.copy()
        bad = rng.choice(len(obs), size=len(obs) // 20, replace=False)
        corrupted[bad, 2:4] += rng.normal(0, 200, (len(bad), 2))

        noisy_points = points + rng.normal(0, 0.02, points.shape)
        from sfmkit.core.metrics import rotation_error_deg

        robust = solver(scene.K, images, poses, noisy_points, corrupted,
                        loss="huber", f_scale=4.0)
        plain = solver(scene.K, images, poses, noisy_points, corrupted, loss="linear")

        err = lambda r: max(rotation_error_deg(r.poses[n].R, poses[n].R) for n in images)  # noqa: E731
        assert err(robust) <= err(plain) + 1e-9

    def test_reports_timing_and_iterations(self, scene, solver):
        images, poses, points, obs = _problem_from_scene(scene, n_cameras=3)
        res = solver(scene.K, images, poses, points + 0.01, obs)
        assert res.seconds > 0
        assert res.n_observations == len(obs)
