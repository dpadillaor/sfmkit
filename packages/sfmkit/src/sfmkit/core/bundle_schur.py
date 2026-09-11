"""Bundle adjustment by a Levenberg-Marquardt of our own: analytic Jacobian, Schur complement.

The problem is ``bundle.solve_bundle``'s, gauge and robust loss included; only
the solver differs. scipy's ``least_squares`` is told nothing of the problem's
shape: it differences the residuals for a Jacobian and solves each step
iteratively over every unknown at once. Here the Jacobian is written out, and
each step eliminates the points first. An observation depends on one camera and
one point, so the points' part of the normal equations is a 3x3 block per point,
inverted one point at a time; what is left, the Schur complement, involves the
cameras alone, six unknowns each, and is solved directly. Ceres and COLMAP solve
bundles the same way.
"""

from __future__ import annotations

import time

import numpy as np

from sfmkit.core.bundle import BundleProblem, BundleResult
from sfmkit.core.geometry import rodrigues
from sfmkit.core.types import Pose

__all__ = ["LOSSES", "solve_bundle_schur"]

LOSSES = ("huber", "linear")


def _skew(v: np.ndarray) -> np.ndarray:
    """``(M, 3, 3)`` cross-product matrices of ``(M, 3)`` vectors."""
    S = np.zeros((len(v), 3, 3))
    S[:, 0, 1], S[:, 0, 2] = -v[:, 2], v[:, 1]
    S[:, 1, 0], S[:, 1, 2] = v[:, 2], -v[:, 0]
    S[:, 2, 0], S[:, 2, 1] = -v[:, 1], v[:, 0]
    return S


def _tangent(t: np.ndarray) -> np.ndarray:
    """``(3, 2)``: two orthonormal directions orthogonal to the unit vector ``t``."""
    b1 = np.cross(t, np.eye(3)[np.argmin(np.abs(t))])
    b1 /= np.linalg.norm(b1)
    return np.column_stack([b1, np.cross(t, b1)])


def _robust(e: np.ndarray, loss: str, f: float) -> tuple[float, np.ndarray]:
    """The cost of residuals ``e`` and each residual's weight in the next step.

    As scipy's ``least_squares``: the loss applies to u and v apart, and Huber's
    is ``0.5 * f**2 * rho((e / f)**2)``. The weights make the step iteratively
    reweighted least squares, which has the same minimum.
    """
    if loss == "linear":
        return 0.5 * float(np.sum(e * e)), np.ones_like(e)
    a = np.abs(e)
    inside = a <= f
    cost = 0.5 * float(np.sum(np.where(inside, a * a, 2 * f * a - f * f)))
    return cost, np.where(inside, 1.0, f / np.where(inside, 1.0, a))


class _Groups:
    """Sums of the rows that share a label; the labels are sorted once, not per sum."""

    def __init__(self, labels: np.ndarray, n: int):
        self.order = np.argsort(labels, kind="stable")
        ordered = labels[self.order]
        self.starts = np.flatnonzero(np.r_[True, ordered[1:] != ordered[:-1]][:len(ordered)])
        self.labels = ordered[self.starts]
        self.n = n

    def sum(self, values: np.ndarray) -> np.ndarray:
        out = np.zeros((self.n, *values.shape[1:]))
        if len(self.order):
            out[self.labels] = np.add.reduceat(values[self.order], self.starts, axis=0)
        return out


def _pairs(point: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Every ordered pair of observations of one point, itself with itself included."""
    order = np.argsort(point, kind="stable")
    ordered = point[order]
    starts = np.flatnonzero(np.r_[True, ordered[1:] != ordered[:-1]])
    lengths = np.diff(np.r_[starts, len(ordered)])
    a, b = [], []
    for n in np.unique(lengths):  # the tracks of one length at once
        idx = order[starts[lengths == n][:, None] + np.arange(n)]
        a.append(np.repeat(idx, n, axis=1).ravel())
        b.append(np.tile(idx, (1, n)).ravel())
    return np.concatenate(a), np.concatenate(b)


class SchurBundle:
    """One bundle's observations, and the Levenberg-Marquardt step on them.

    Camera 0 is held fixed and camera 1's translation stays unit length, as in
    ``BundleProblem``. A camera moves by ``R <- exp(w) R, t <- t + dt``; camera
    1's ``dt`` lies in the plane tangent to its unit sphere.
    """

    def __init__(self, K, n_cameras: int, n_points: int, observations):
        self.K = np.asarray(K, dtype=float)
        if not np.allclose(self.K[2], [0, 0, 1]):
            raise ValueError("K's last row must be [0, 0, 1]")
        obs = np.asarray(observations, dtype=float)
        self.point = obs[:, 0].astype(np.intp)
        self.cam = obs[:, 1].astype(np.intp)
        self.uv = obs[:, 2:4]
        self.n_cameras, self.n_points = n_cameras, n_points
        self.by_cam = _Groups(self.cam, n_cameras)
        self.by_point = _Groups(self.point, n_points)
        # Two observations of one point couple their cameras in the reduced system.
        self.a, self.b = _pairs(self.point)
        self.by_block = _Groups(self.cam[self.a] * n_cameras + self.cam[self.b], n_cameras ** 2)

    def _project(self, R, t, X):
        RX = np.einsum("mij,mj->mi", R[self.cam], X[self.point])
        Xc = RX + t[self.cam]
        ok = Xc[:, 2] > 0
        z = np.where(ok, Xc[:, 2], 1.0)
        proj = Xc @ self.K[:2].T / z[:, None]
        # A point behind its camera adds nothing, to the cost or to the step.
        return RX, z, proj, ok, np.where(ok[:, None], self.uv - proj, 0.0)

    def residual(self, R, t, X) -> np.ndarray:
        """``(M, 2)`` observed minus projected, in pixels."""
        return self._project(R, t, X)[-1]

    def linearize(self, R, t, X):
        """The residuals, and their derivatives by each observation's camera and point.

        Returns ``e`` ``(M, 2)``, ``Jc`` ``(M, 2, 6)`` by the camera's rotation
        then translation, and ``Jp`` ``(M, 2, 3)``.
        """
        RX, z, proj, ok, e = self._project(R, t, X)
        # d proj / d x_cam; the residual's derivative is its opposite.
        A = (self.K[:2][None] - proj[:, :, None] * np.array([0.0, 0.0, 1.0])) / z[:, None, None]
        A[~ok] = 0.0
        Jc = np.concatenate([A @ _skew(RX), -A], axis=2)
        Jp = -A @ R[self.cam]
        return e, Jc, Jp

    def normal_equations(self, e, w, Jc, Jp) -> dict:
        """The blocks of ``J^T W J`` and ``J^T W e``: per camera, per point, per observation."""
        Jcw = Jc * w[:, :, None]
        return {
            "U": self.by_cam.sum(np.einsum("mki,mkj->mij", Jcw, Jc)),
            "V": self.by_point.sum(np.einsum("mki,mkj->mij", Jp * w[:, :, None], Jp)),
            "W": np.einsum("mki,mkj->mij", Jcw, Jp),
            "gc": self.by_cam.sum(np.einsum("mki,mk->mi", Jcw, e)),
            "gp": self.by_point.sum(np.einsum("mki,mk->mi", Jp * w[:, :, None], e)),
        }

    def gauge(self, t1: np.ndarray) -> np.ndarray:
        """``(6N, 6N - 7)``: the directions the cameras are free to move in."""
        n = 6 * self.n_cameras
        G = np.zeros((n, n - 7))
        G[6:9, 0:3] = np.eye(3)
        G[9:12, 3:5] = _tangent(t1)
        G[12:, 5:] = np.eye(n - 12)
        return G

    def solve(self, ne: dict, lam: float, t1: np.ndarray):
        """The damped step: each camera's ``(w, dt)`` ``(N, 6)``, each point's move
        ``(P, 3)``, and the cost reduction the linear model predicts for them."""
        N, U, V, W, gc, gp = self.n_cameras, ne["U"], ne["V"], ne["W"], ne["gc"], ne["gp"]
        Dp = np.clip(np.einsum("pii->pi", V), 1e-6, 1e32)
        Vinv = np.linalg.inv(V + lam * Dp[:, :, None] * np.eye(3))
        Y = W @ Vinv[self.point]
        S = self.by_block.sum(-(Y[self.a] @ W[self.b].transpose(0, 2, 1))).reshape(N, N, 6, 6)
        S[np.arange(N), np.arange(N)] += U
        S = S.transpose(0, 2, 1, 3).reshape(6 * N, 6 * N)
        rhs = (-gc + self.by_cam.sum(np.einsum("mij,mj->mi", Y, gp[self.point]))).ravel()

        G = self.gauge(t1)
        Sg = G.T @ S @ G
        Dc = np.clip(np.diag(G.T @ _block_diag(U) @ G), 1e-6, 1e32)
        Sg[np.diag_indices_from(Sg)] += lam * Dc
        step = np.linalg.solve(Sg, G.T @ rhs)
        dc = (G @ step).reshape(N, 6)
        back = self.by_point.sum(np.einsum("mji,mj->mi", W, dc[self.cam]))
        dp = np.einsum("pij,pj->pi", Vinv, -gp - back)
        # Of the model 0.5 |sqrt(W) (e + J d)|^2, with (H + lam D) d = -g.
        predicted = 0.5 * (lam * (step @ (Dc * step) + np.sum(Dp * dp * dp))
                           - np.sum(gc * dc) - np.sum(gp * dp))
        return dc, dp, float(predicted)


def _block_diag(U: np.ndarray) -> np.ndarray:
    n = len(U)
    out = np.zeros((6 * n, 6 * n))
    for i in range(n):
        out[6 * i:6 * i + 6, 6 * i:6 * i + 6] = U[i]
    return out


def _moved(R, t, X, dc, dp):
    R = np.stack([rodrigues(w) @ r for w, r in zip(dc[:, :3], R, strict=True)])
    t = t + dc[:, 3:]
    t[1] /= np.linalg.norm(t[1])
    return R, t, X + dp


def solve_bundle_schur(
    K, images, poses, points, observations, *, max_iterations: int = 200,
    loss: str = "huber", f_scale: float = 4.0, ftol: float = 1e-6, xtol: float = 1e-8,
) -> BundleResult:
    """Refine poses and points by minimising reprojection error; ``solve_bundle``'s
    arguments and result, another solver.

    Stops when an accepted step lowers the cost by less than ``ftol`` of it, or
    moves the unknowns by less than ``xtol`` of them. ``ftol`` is Ceres's
    default: with the Huber loss the last stretch converges slowly, and on
    Valencia 1e-8 takes five times the iterations to move a camera 0.002°.
    ``n_iterations`` counts Jacobians, as scipy's ``njev``.
    """
    if loss not in LOSSES:
        raise ValueError(f"loss must be one of {LOSSES}, not {loss!r}")
    images = list(images)
    prob = BundleProblem(K, images, poses, points, observations)  # for the same RMSE
    rmse = lambda r: float(np.sqrt(np.mean(r.reshape(-1) ** 2) * 2))  # noqa: E731
    before = rmse(prob.residual(prob.pack(poses, points)))

    t0 = time.perf_counter()
    R = np.stack([poses[n].R for n in images]).astype(float)
    t = np.stack([poses[n].t for n in images]).astype(float)
    R[0], t[0] = np.eye(3), 0.0
    t[1] /= np.linalg.norm(t[1]) or 1.0
    X = np.array(points, dtype=float)
    bundle = SchurBundle(K, len(images), len(X), observations)

    e, Jc, Jp = bundle.linearize(R, t, X)
    cost, w = _robust(e, loss, f_scale)
    ne = bundle.normal_equations(e, w, Jc, Jp)
    lam, nu, n_jacobians = 1e-4, 2.0, 1
    for _ in range(max_iterations):
        try:
            dc, dp, predicted = bundle.solve(ne, lam, t[1])
        except np.linalg.LinAlgError:
            predicted = -1.0
        ratio = -1.0
        if predicted > 0:
            R2, t2, X2 = _moved(R, t, X, dc, dp)
            cost2, _ = _robust(bundle.residual(R2, t2, X2), loss, f_scale)
            ratio = (cost - cost2) / predicted
        if not ratio > 0:  # worse, or not a number
            lam, nu = lam * nu, nu * 2
            if lam > 1e16:
                break
            continue
        small = np.sqrt(np.sum(dc * dc) + np.sum(dp * dp)) <= xtol * (
            np.sqrt(np.sum(t * t) + np.sum(X * X)) + xtol)
        converged = small or (cost - cost2 < ftol * cost and ratio > 0.25)
        R, t, X, cost = R2, t2, X2, cost2
        lam, nu = lam * max(1 / 3, 1 - (2 * ratio - 1) ** 3), 2.0
        if converged:
            break
        e, Jc, Jp = bundle.linearize(R, t, X)
        _, w = _robust(e, loss, f_scale)
        ne = bundle.normal_equations(e, w, Jc, Jp)
        n_jacobians += 1
    seconds = time.perf_counter() - t0

    new_poses = {n: Pose(R[i], t[i]) for i, n in enumerate(images)}
    after = rmse(prob.residual(prob.pack(new_poses, X)))
    return BundleResult(poses=new_poses, points=X, rmse_before=before, rmse_after=after,
                        n_iterations=n_jacobians, seconds=seconds,
                        n_observations=prob.n_residuals // 2)
