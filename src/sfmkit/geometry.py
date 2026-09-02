"""Two-view geometry and triangulation. Pure functions, row-major arrays.

Nothing here reads files, prints, plots, or draws on a global RNG.
"""

from __future__ import annotations

import numpy as np

from sfmkit.types import Pose

__all__ = [
    "rodrigues", "log_rotation", "skew",
    "normalize_points", "eight_point", "fundamental_to_essential",
    "essential_to_poses", "recover_pose", "triangulate_two_view",
    "triangulate_multi_view", "project", "reprojection_errors",
    "sampson_distance", "symmetric_epipolar_distance", "decompose_projection",
]


def skew(v: np.ndarray) -> np.ndarray:
    """Cross-product matrix of a 3-vector."""
    x, y, z = np.asarray(v, dtype=float).ravel()
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def rodrigues(w: np.ndarray) -> np.ndarray:
    """Axis-angle to rotation matrix, in closed form.

    Equivalent to ``scipy.linalg.expm(skew(w))`` to machine precision, but
    without the general Pade algorithm (and without the object-dtype array the
    original ``crossMatrix`` built).
    """
    w = np.asarray(w, dtype=float).ravel()
    theta = float(np.linalg.norm(w))
    if theta < 1e-12:
        return np.eye(3)
    K = skew(w / theta)
    return np.eye(3) + np.sin(theta) * K + (1.0 - np.cos(theta)) * (K @ K)


def log_rotation(R: np.ndarray) -> np.ndarray:
    """Rotation matrix to axis-angle. Inverse of :func:`rodrigues`."""
    R = np.asarray(R, dtype=float)
    c = np.clip((np.trace(R) - 1.0) / 2.0, -1.0, 1.0)
    theta = float(np.arccos(c))
    if theta < 1e-12:
        return np.zeros(3)
    if abs(theta - np.pi) < 1e-6:
        # Near pi the antisymmetric part vanishes; recover the axis from R + I.
        A = (R + np.eye(3)) / 2.0
        axis = np.sqrt(np.clip(np.diag(A), 0.0, None))
        k = int(np.argmax(axis))
        if axis[k] > 0:
            axis = A[:, k] / axis[k]
        return theta * axis / np.linalg.norm(axis)
    v = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
    return theta * v / (2.0 * np.sin(theta))


def normalize_points(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Hartley normalisation: centre at the origin, mean distance sqrt(2).

    Returns the transformed ``(N, 2)`` points and the ``3x3`` transform applied.
    Skipping this is the classic way to get a badly conditioned eight-point
    solution on pixel coordinates in the thousands.
    """
    x = np.asarray(x, dtype=float)
    mu = x.mean(axis=0)
    d = np.linalg.norm(x - mu, axis=1).mean()
    s = np.sqrt(2.0) / d if d > 0 else 1.0
    T = np.array([[s, 0.0, -s * mu[0]], [0.0, s, -s * mu[1]], [0.0, 0.0, 1.0]])
    return (x - mu) * s, T


def eight_point(x0: np.ndarray, x1: np.ndarray) -> np.ndarray:
    """Fundamental matrix from >= 8 correspondences, normalised and rank-2 enforced."""
    x0 = np.asarray(x0, dtype=float)
    x1 = np.asarray(x1, dtype=float)
    if len(x0) < 8:
        raise ValueError(f"eight_point needs at least 8 correspondences, got {len(x0)}")

    n0, T0 = normalize_points(x0)
    n1, T1 = normalize_points(x1)
    u0, v0 = n0[:, 0], n0[:, 1]
    u1, v1 = n1[:, 0], n1[:, 1]
    A = np.column_stack([u1 * u0, u1 * v0, u1, v1 * u0, v1 * v0, v1, u0, v0, np.ones(len(u0))])

    _, _, Vt = np.linalg.svd(A)
    F = Vt[-1].reshape(3, 3)

    # A fundamental matrix is rank 2; the linear solution generally is not.
    U, s, Vt2 = np.linalg.svd(F)
    F = U @ np.diag([s[0], s[1], 0.0]) @ Vt2

    F = T1.T @ F @ T0
    return F / (np.linalg.norm(F) or 1.0)


def fundamental_to_essential(F: np.ndarray, K0: np.ndarray, K1: np.ndarray) -> np.ndarray:
    """``E = K1^T F K0``, with the two equal singular values enforced."""
    E = np.asarray(K1, dtype=float).T @ np.asarray(F, dtype=float) @ np.asarray(K0, dtype=float)
    U, _, Vt = np.linalg.svd(E)
    if np.linalg.det(U) < 0:
        U[:, -1] *= -1
    if np.linalg.det(Vt) < 0:
        Vt[-1] *= -1
    return U @ np.diag([1.0, 1.0, 0.0]) @ Vt


def essential_to_poses(E: np.ndarray) -> list[Pose]:
    """The four candidate poses of camera 1 relative to camera 0."""
    U, _, Vt = np.linalg.svd(np.asarray(E, dtype=float))
    if np.linalg.det(U) < 0:
        U[:, -1] *= -1
    if np.linalg.det(Vt) < 0:
        Vt[-1] *= -1
    W = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    R1, R2, t = U @ W @ Vt, U @ W.T @ Vt, U[:, 2]
    return [Pose(R1, t), Pose(R1, -t), Pose(R2, t), Pose(R2, -t)]


def _cheirality_count(pose: Pose, K: np.ndarray, x0: np.ndarray, x1: np.ndarray) -> int:
    """How many correspondences triangulate in front of both cameras."""
    X = triangulate_two_view(x0, x1, K, Pose.identity(), K, pose)
    ok = np.isfinite(X).all(axis=1)
    if not ok.any():
        return 0
    return int((ok & (X[:, 2] > 0) & (pose.transform(np.nan_to_num(X))[:, 2] > 0)).sum())


def recover_pose(E: np.ndarray, K: np.ndarray, x0: np.ndarray, x1: np.ndarray) -> Pose:
    """Pick the one of four decompositions with points in front of both cameras."""
    cands = essential_to_poses(E)
    counts = [_cheirality_count(p, K, x0, x1) for p in cands]
    return cands[int(np.argmax(counts))]


def triangulate_two_view(
    x0: np.ndarray, x1: np.ndarray, K0: np.ndarray, pose0: Pose, K1: np.ndarray, pose1: Pose
) -> np.ndarray:
    """Linear triangulation of ``(N, 2)`` correspondences. Returns ``(N, 3)``."""
    P0, P1 = pose0.projection_matrix(K0), pose1.projection_matrix(K1)
    x0 = np.asarray(x0, dtype=float)
    x1 = np.asarray(x1, dtype=float)

    A = np.empty((len(x0), 4, 4))
    A[:, 0] = x0[:, 0, None] * P0[2] - P0[0]
    A[:, 1] = x0[:, 1, None] * P0[2] - P0[1]
    A[:, 2] = x1[:, 0, None] * P1[2] - P1[0]
    A[:, 3] = x1[:, 1, None] * P1[2] - P1[1]

    _, _, Vt = np.linalg.svd(A)
    X = Vt[:, -1, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        X = X[:, :3] / X[:, 3:4]
    return X


def triangulate_multi_view(
    observations: list[tuple[np.ndarray, np.ndarray]],
) -> np.ndarray:
    """Triangulate one point from N views.

    ``observations`` is a list of ``(xy, P)``: a 2-vector image point and its
    3x4 projection matrix. Two views are the minimum; more views tighten depth,
    which is exactly what a star-shaped graph never gets to exploit.
    """
    if len(observations) < 2:
        raise ValueError("triangulate_multi_view needs at least 2 observations")
    rows = []
    for xy, P in observations:
        rows.append(xy[0] * P[2] - P[0])
        rows.append(xy[1] * P[2] - P[1])
    _, _, Vt = np.linalg.svd(np.asarray(rows, dtype=float))
    X = Vt[-1]
    if abs(X[3]) < 1e-12:
        return np.full(3, np.nan)
    return X[:3] / X[3]


def project(points: np.ndarray, K: np.ndarray, pose: Pose) -> np.ndarray:
    """Project world points ``(N, 3)`` to pixels ``(N, 2)``. Points behind the camera give NaN."""
    Xc = pose.transform(np.asarray(points, dtype=float))
    z = Xc[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        uv = (np.asarray(K, dtype=float) @ Xc.T).T
        uv = uv[:, :2] / uv[:, 2:3]
    return np.where((z > 0)[:, None], uv, np.nan)


def reprojection_errors(points, observed, K, pose) -> np.ndarray:
    """Per-point pixel distance between projection and observation."""
    return np.linalg.norm(project(points, K, pose) - np.asarray(observed, dtype=float), axis=1)


def _to_homogeneous(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return np.hstack([x, np.ones((len(x), 1))])


def sampson_distance(F: np.ndarray, x0: np.ndarray, x1: np.ndarray) -> np.ndarray:
    """First-order geometric error. The right residual for fundamental-matrix RANSAC."""
    h0, h1 = _to_homogeneous(x0), _to_homogeneous(x1)
    Fx0, Ftx1 = h0 @ F.T, h1 @ F
    num = np.einsum("ij,ij->i", h1, Fx0) ** 2
    den = Fx0[:, 0] ** 2 + Fx0[:, 1] ** 2 + Ftx1[:, 0] ** 2 + Ftx1[:, 1] ** 2
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.sqrt(np.where(den > 0, num / den, np.inf))


def symmetric_epipolar_distance(F: np.ndarray, x0: np.ndarray, x1: np.ndarray) -> np.ndarray:
    """Mean point-to-epipolar-line distance in both images."""
    h0, h1 = _to_homogeneous(x0), _to_homogeneous(x1)
    l1, l0 = h0 @ F.T, h1 @ F
    with np.errstate(divide="ignore", invalid="ignore"):
        d1 = np.abs(np.einsum("ij,ij->i", h1, l1)) / np.linalg.norm(l1[:, :2], axis=1)
        d0 = np.abs(np.einsum("ij,ij->i", h0, l0)) / np.linalg.norm(l0[:, :2], axis=1)
    return (d0 + d1) / 2.0


def decompose_projection(P: np.ndarray) -> tuple[np.ndarray, Pose]:
    """Split a 3x4 projection matrix into ``K`` and a world-to-camera pose.

    Uses RQ on the left 3x3 block, then fixes signs so that ``K`` has a positive
    diagonal and ``R`` is a proper rotation.
    """
    from scipy.linalg import rq

    P = np.asarray(P, dtype=float)
    K, R = rq(P[:, :3])
    S = np.diag(np.sign(np.diag(K)))
    K, R = K @ S, S @ R
    if np.linalg.det(R) < 0:
        R, K = -R, K  # a sign flip on R alone keeps K unchanged
    t = np.linalg.solve(K, P[:, 3])
    return K / K[2, 2], Pose(R, t)
