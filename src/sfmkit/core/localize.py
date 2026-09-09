"""Visual localisation: place a query image against an existing reconstruction.

This is what the original called "the old camera pose". The name matters: the
operation is standard visual localisation -- match the query against registered
images, lift the matches to the map's 3D points through the tracks, and solve
PnP -- and framing it that way is what makes the two-stage structure (build a
map, then localise into it) explicit.

The query is deliberately excluded from the reconstruction itself. A historical
photograph with different intrinsics, different lighting and a century of scene
change should not be allowed to distort the map it is being located against.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from sfmkit.core.geometry import decompose_projection, reprojection_errors
from sfmkit.core.robust import ransac_dlt, ransac_pnp
from sfmkit.core.types import Matches, Pose, Reconstruction

__all__ = ["LocalizationResult", "localize_image"]


@dataclass
class LocalizationResult:
    pose: Pose
    n_correspondences: int
    n_inliers: int
    rmse: float
    seed: int
    K: np.ndarray | None = None  # estimated when the query's intrinsics are unknown


def _query_to_map_correspondences(
    rec: Reconstruction, matches: list[Matches], query: str
) -> tuple[np.ndarray, np.ndarray]:
    """Collect 3D-2D correspondences between the map and the query image.

    A match links a query keypoint to a keypoint in a registered image; the
    tracks say which 3D point that registered keypoint belongs to. Every such
    link is one 3D-2D correspondence.
    """
    # keypoint (image, index) -> track id, for registered images only.
    lookup: dict[tuple[str, int], int] = {}
    ok = rec.triangulated_mask()
    for tid, track in enumerate(rec.tracks):
        if not ok[tid]:
            continue
        for img, kp in track.observations.items():
            if img in rec.poses:
                lookup[(img, int(kp))] = tid

    points_3d: list[np.ndarray] = []
    points_2d: list[np.ndarray] = []
    seen: set[tuple[int, int]] = set()

    for m in matches:
        if query == m.image1:
            other, q_kp_all, o_first = m.image0, m.keypoints1, True
        elif query == m.image0:
            other, q_kp_all, o_first = m.image1, m.keypoints0, False
        else:
            continue
        if other not in rec.poses:
            continue
        for a, b in m.verified_pairs():
            o_idx, q_idx = (int(a), int(b)) if o_first else (int(b), int(a))
            tid = lookup.get((other, o_idx))
            if tid is None or (tid, q_idx) in seen:
                continue
            seen.add((tid, q_idx))
            points_3d.append(rec.points[tid])
            points_2d.append(q_kp_all[q_idx])

    if not points_3d:
        return np.zeros((0, 3)), np.zeros((0, 2))
    return np.asarray(points_3d), np.asarray(points_2d)


def localize_image(
    rec: Reconstruction,
    matches: list[Matches],
    query: str,
    *,
    K: np.ndarray | None = None,
    threshold: float = 8.0,
    seed: int = 0,
) -> LocalizationResult | None:
    """Estimate the query camera's pose. Returns ``None`` if it cannot be solved.

    When ``K`` is given, this is a PnP problem. When it is not -- the usual case
    for a historical photograph, whose camera is nothing like the one that built
    the map -- a full projection matrix is estimated by DLT and decomposed, so
    the focal length is recovered rather than assumed.

    Assuming the map's intrinsics instead is not a small approximation: here the
    modern images are 4032x2268 with f = 3544 px while the historical plate is
    557x418, and forcing the former onto the latter puts the camera several times
    further away than the entire set of viewpoints.
    """
    X, uv = _query_to_map_correspondences(rec, matches, query)
    if len(X) < 6:
        return None

    if K is not None:
        K = np.asarray(K, dtype=float)
        res = ransac_pnp(X, uv, K, threshold=threshold, seed=seed)
        if res.model is None:
            return None
        pose, K_est = res.model, K
    else:
        res = ransac_dlt(X, uv, threshold=threshold, seed=seed)
        if res.model is None:
            return None
        try:
            K_est, pose = decompose_projection(res.model)
        except np.linalg.LinAlgError:
            return None

    errs = reprojection_errors(X[res.inliers], uv[res.inliers], K_est, pose)
    errs = errs[np.isfinite(errs)]
    return LocalizationResult(
        pose=pose,
        n_correspondences=len(X),
        n_inliers=int(res.n_inliers),
        rmse=float(np.sqrt(np.mean(errs**2))) if errs.size else float("nan"),
        seed=seed,
        K=K_est,
    )
