"""Our Levenberg-Marquardt against the problem it solves and against scipy's solve."""

import numpy as np
import pytest

from sfmkit.core.bundle import solve_bundle
from sfmkit.core.bundle_schur import SchurBundle, _moved, _pairs, _robust, solve_bundle_schur
from sfmkit.core.metrics import rotation_error_deg
from test_bundle import _problem_from_scene


def _state(scene, n_cameras=5, noise=0.05, seed=0):
    images, poses, points, obs = _problem_from_scene(scene, n_cameras=n_cameras)
    rng = np.random.default_rng(seed)
    return images, poses, points, points + rng.normal(0, noise, points.shape), obs


def test_the_jacobian_is_the_residuals_derivative(scene):
    """Against central differences, through the very update a step applies."""
    images, poses, _, X, obs = _state(scene)
    R = np.stack([poses[n].R for n in images])
    t = np.stack([poses[n].t for n in images])
    bundle = SchurBundle(scene.K, len(images), len(X), obs)
    e, Jc, Jp = bundle.linearize(R, t, X)
    h = 1e-6
    for c in range(2, len(images)):
        for k in range(6):
            d = np.zeros((len(images), 6))
            d[c, k] = h
            plus = bundle.residual(*_moved(R, t, X, d, 0 * X))
            minus = bundle.residual(*_moved(R, t, X, -d, 0 * X))
            seen = bundle.cam == c
            num = (plus - minus)[seen] / (2 * h)
            assert np.allclose(num, Jc[seen][:, :, k], rtol=1e-6, atol=1e-4)
    for p in range(0, len(X), 29):
        for k in range(3):
            d = np.zeros_like(X)
            d[p, k] = h
            num = (bundle.residual(R, t, X + d) - bundle.residual(R, t, X - d)) / (2 * h)
            seen = bundle.point == p
            assert np.allclose(num[seen], Jp[seen][:, :, k], rtol=1e-6, atol=1e-4)


def test_every_pair_of_observations_of_a_point():
    a, b = _pairs(np.array([2, 0, 2, 1, 2, 0]))
    pairs = set(zip(a.tolist(), b.tolist(), strict=True))
    assert len(a) == 3 * 3 + 2 * 2 + 1
    assert pairs == {(i, j) for i in (0, 2, 4) for j in (0, 2, 4)} | {
        (i, j) for i in (1, 5) for j in (1, 5)} | {(3, 3)}


def test_huber_is_scipys():
    e = np.array([[0.5, -3.0], [10.0, -40.0]])
    cost, w = _robust(e, "huber", 4.0)
    rho = lambda z: np.where(z <= 1, z, 2 * np.sqrt(z) - 1)  # noqa: E731, scipy's huber
    assert np.isclose(cost, 0.5 * 16 * rho((e / 4) ** 2).sum())
    assert np.allclose(w, [[1, 1], [0.4, 0.1]])


def test_the_gauge_holds(scene):
    images, poses, _, X, obs = _state(scene)
    res = solve_bundle_schur(scene.K, images, poses, X, obs)
    assert np.allclose(res.poses[images[0]].R, np.eye(3))
    assert np.allclose(res.poses[images[0]].t, 0)
    assert np.isclose(np.linalg.norm(res.poses[images[1]].t), 1.0)


@pytest.mark.parametrize("loss", ["linear", "huber"])
def test_it_meets_scipy_or_does_better(scene, loss):
    """The same minimum, reached in fewer iterations; with Huber, scipy's stops short of it."""
    images, poses, truth, X, obs = _state(scene, n_cameras=4)
    ours = solve_bundle_schur(scene.K, images, poses, X, obs, loss=loss)
    theirs = solve_bundle(scene.K, images, poses, X, obs, loss=loss)
    assert ours.rmse_after <= theirs.rmse_after + 1e-6
    assert ours.n_iterations < theirs.n_iterations
    for n in images:
        assert rotation_error_deg(ours.poses[n].R, poses[n].R) < 1e-3
    seen_twice = np.bincount(obs[:, 0].astype(int), minlength=len(truth)) >= 2
    assert np.abs(ours.points - truth)[seen_twice].max() < 1e-4


def test_an_unknown_loss_is_refused(scene):
    images, poses, points, _, obs = _state(scene, n_cameras=3)
    with pytest.raises(ValueError, match="loss"):
        solve_bundle_schur(scene.K, images, poses, points, obs, loss="cauchy")
