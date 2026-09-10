"""Robust estimation by RANSAC.

Every estimator takes an explicit ``seed`` and uses no global random state."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from sfmkit.core.geometry import eight_point, sampson_distance
from sfmkit.core.types import Pose

__all__ = ["RansacResult", "ransac_fundamental", "ransac_pnp", "ransac_dlt"]


@dataclass(eq=False)
class RansacResult:
    """The outcome of a RANSAC fit.

    ``model`` is ``None`` when no consensus was found, in which case
    ``converged`` is False and ``inliers`` is all-False rather than absent.
    """

    model: np.ndarray | Pose | None
    inliers: np.ndarray  # bool mask over the input correspondences
    n_iterations: int
    converged: bool

    @property
    def n_inliers(self) -> int:
        return int(self.inliers.sum())


def _adaptive_iterations(n_inliers: int, n_total: int, sample_size: int,
                         confidence: float, max_iter: int) -> int:
    """How many trials are still needed given the inlier ratio seen so far."""
    if n_total == 0 or n_inliers < sample_size:
        return max_iter
    w = n_inliers / n_total
    denom = 1.0 - w**sample_size
    if denom <= 1e-12:
        return 1
    return min(max_iter, int(np.ceil(np.log(1.0 - confidence) / np.log(denom))))


def ransac_fundamental(
    x0: np.ndarray,
    x1: np.ndarray,
    *,
    threshold: float = 4.0,
    max_iterations: int = 1000,
    confidence: float = 0.999,
    seed: int | None = None,
) -> RansacResult:
    """Robustly fit a fundamental matrix to ``(N, 2)`` correspondences.

    Hypotheses are scored by Sampson distance, the first-order geometric error.
    Terminates once ``confidence`` is reached, so a clean pair costs far fewer
    than ``max_iterations`` trials.
    """
    x0 = np.asarray(x0, dtype=float)
    x1 = np.asarray(x1, dtype=float)
    n = len(x0)
    if n < 8:
        return RansacResult(None, np.zeros(n, dtype=bool), 0, False)

    rng = np.random.default_rng(seed)
    best_inliers = np.zeros(n, dtype=bool)
    best_count = 0
    iters = max_iterations
    i = 0

    while i < iters:
        idx = rng.choice(n, 8, replace=False)
        try:
            F = eight_point(x0[idx], x1[idx])
        except (ValueError, np.linalg.LinAlgError):
            i += 1
            continue
        inliers = sampson_distance(F, x0, x1) < threshold
        count = int(inliers.sum())
        if count > best_count:
            best_count, best_inliers = count, inliers
            iters = min(iters, _adaptive_iterations(count, n, 8, confidence, max_iterations))
        i += 1

    if best_count < 8:
        # best_inliers is initialised before the loop, so a run in which no
        # sample ever improves still returns a well-formed failure.
        return RansacResult(None, best_inliers, i, False)

    F = eight_point(x0[best_inliers], x1[best_inliers])
    final = sampson_distance(F, x0, x1) < threshold
    if int(final.sum()) >= 8:
        F = eight_point(x0[final], x1[final])
        best_inliers = final
    return RansacResult(F, best_inliers, i, True)


def ransac_pnp(
    points_3d: np.ndarray,
    points_2d: np.ndarray,
    K: np.ndarray,
    *,
    threshold: float = 4.0,
    max_iterations: int = 1000,
    confidence: float = 0.999,
    seed: int | None = None,
) -> RansacResult:
    """Camera pose from 3D-2D correspondences with known intrinsics.

    Wraps ``cv2.solvePnPRansac``, seeded for reproducibility, and refines the
    result on the inliers alone.
    """
    import cv2

    points_3d = np.ascontiguousarray(points_3d, dtype=np.float64)
    points_2d = np.ascontiguousarray(points_2d, dtype=np.float64)
    n = len(points_3d)
    if n < 6:
        return RansacResult(None, np.zeros(n, dtype=bool), 0, False)

    if seed is not None:
        cv2.setRNGSeed(int(seed))

    ok, rvec, tvec, inl = cv2.solvePnPRansac(
        points_3d,
        points_2d,
        np.asarray(K, dtype=np.float64),
        np.zeros((4, 1)),
        reprojectionError=float(threshold),
        confidence=float(confidence),
        iterationsCount=int(max_iterations),
        flags=cv2.SOLVEPNP_EPNP,
    )
    mask = np.zeros(n, dtype=bool)
    if not ok or inl is None or len(inl) < 6:
        return RansacResult(None, mask, max_iterations, False)
    mask[inl.ravel()] = True

    # Refine on the inliers only.
    rvec, tvec = cv2.solvePnPRefineLM(
        points_3d[mask], points_2d[mask], np.asarray(K, dtype=np.float64),
        np.zeros((4, 1)), rvec, tvec,
    )
    R, _ = cv2.Rodrigues(rvec)
    return RansacResult(Pose(R, tvec.ravel()), mask, max_iterations, True)


def _dlt(points_3d: np.ndarray, points_2d: np.ndarray) -> np.ndarray:
    """Direct linear transform: the 3x4 projection matrix from >= 6 correspondences.

    Both sides are normalised before the solve (Hartley conditioning), otherwise
    pixel coordinates in the thousands against world coordinates near 1 give a
    hopelessly conditioned system.
    """
    X = np.asarray(points_3d, dtype=float)
    x = np.asarray(points_2d, dtype=float)
    n = len(X)
    if n < 6:
        raise ValueError("DLT needs at least 6 correspondences")

    cx, cy = x.mean(axis=0)
    sx = np.sqrt(2.0) / (np.linalg.norm(x - [cx, cy], axis=1).mean() or 1.0)
    T = np.array([[sx, 0, -sx * cx], [0, sx, -sx * cy], [0, 0, 1.0]])
    xn = (x - [cx, cy]) * sx

    cX = X.mean(axis=0)
    sX = np.sqrt(3.0) / (np.linalg.norm(X - cX, axis=1).mean() or 1.0)
    U = np.eye(4)
    U[:3, :3] *= sX
    U[:3, 3] = -sX * cX
    Xn = (X - cX) * sX

    A = np.zeros((2 * n, 12))
    Xh = np.hstack([Xn, np.ones((n, 1))])
    A[0::2, 0:4] = Xh
    A[0::2, 8:12] = -xn[:, 0:1] * Xh
    A[1::2, 4:8] = Xh
    A[1::2, 8:12] = -xn[:, 1:2] * Xh

    _, _, Vt = np.linalg.svd(A)
    P = Vt[-1].reshape(3, 4)
    P = np.linalg.inv(T) @ P @ U
    return P / (np.linalg.norm(P) or 1.0)


def _projection_errors(P: np.ndarray, X: np.ndarray, x: np.ndarray) -> np.ndarray:
    Xh = np.hstack([X, np.ones((len(X), 1))])
    p = Xh @ P.T
    with np.errstate(divide="ignore", invalid="ignore"):
        uv = p[:, :2] / p[:, 2:3]
    return np.where(np.isfinite(uv).all(axis=1), np.linalg.norm(uv - x, axis=1), np.inf)


def ransac_dlt(
    points_3d: np.ndarray,
    points_2d: np.ndarray,
    *,
    threshold: float = 8.0,
    max_iterations: int = 2000,
    confidence: float = 0.999,
    seed: int | None = None,
) -> RansacResult:
    """Robustly fit a full 3x4 projection matrix, intrinsics unknown.

    Use this when the query camera is not the one that built the map. PnP
    requires a calibration matrix; the DLT recovers all eleven degrees of
    freedom, and ``sfmkit.core.geometry.decompose_projection`` splits the
    result into K, R and t.

    Estimating eleven parameters from six correspondences is less stable than
    PnP, so run several seeds and report the distribution.
    """
    X = np.asarray(points_3d, dtype=float)
    x = np.asarray(points_2d, dtype=float)
    n = len(X)
    if n < 6:
        return RansacResult(None, np.zeros(n, dtype=bool), 0, False)

    rng = np.random.default_rng(seed)
    best_inliers = np.zeros(n, dtype=bool)
    best_count, iters, i = 0, max_iterations, 0

    while i < iters:
        idx = rng.choice(n, 6, replace=False)
        try:
            P = _dlt(X[idx], x[idx])
        except (ValueError, np.linalg.LinAlgError):
            i += 1
            continue
        inliers = _projection_errors(P, X, x) < threshold
        count = int(inliers.sum())
        if count > best_count:
            best_count, best_inliers = count, inliers
            iters = min(iters, _adaptive_iterations(count, n, 6, confidence, max_iterations))
        i += 1

    if best_count < 6:
        return RansacResult(None, best_inliers, i, False)
    return RansacResult(_dlt(X[best_inliers], x[best_inliers]), best_inliers, i, True)
