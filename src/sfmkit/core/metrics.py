"""Compare one reconstruction against another."""

from __future__ import annotations

import numpy as np

from sfmkit.core.types import Pose

__all__ = [
    "rotation_error_deg", "align_to_reference", "scale_between",
    "compare_poses", "rmse_reprojection",
]


def rotation_error_deg(R1: np.ndarray, R2: np.ndarray) -> float:
    """Geodesic angle between two rotations, in degrees."""
    c = (np.trace(np.asarray(R1) @ np.asarray(R2).T) - 1.0) / 2.0
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))


def align_to_reference(poses: dict[str, Pose], reference: str) -> dict[str, Pose]:
    """Re-express every pose in ``reference``'s camera frame."""
    ref = poses[reference]
    return {n: p.relative_to(ref) for n, p in poses.items()}


def scale_between(estimate: dict[str, Pose], truth: dict[str, Pose], image: str) -> float:
    """Scale factor implied by one camera's distance from the origin."""
    d_est = float(np.linalg.norm(estimate[image].center))
    d_gt = float(np.linalg.norm(truth[image].center))
    return d_est / d_gt if d_gt > 1e-12 else float("nan")


def compare_poses(
    estimate: dict[str, Pose],
    truth: dict[str, Pose],
    reference: str,
    *,
    scale_image: str | None = None,
) -> dict:
    """Per-camera rotation and position error after gauge alignment.

    ``scale_image`` names the camera whose baseline fixes scale; by default the
    first shared camera other than the reference is used.
    """
    shared = [n for n in estimate if n in truth]
    if reference not in shared:
        raise ValueError(f"reference {reference!r} is missing from one of the pose sets")

    est = align_to_reference({n: estimate[n] for n in shared}, reference)
    gt = align_to_reference({n: truth[n] for n in shared}, reference)

    if scale_image is None:
        others = [n for n in shared if n != reference]
        if not others:
            raise ValueError("need at least two shared cameras to fix scale")
        scale_image = max(others, key=lambda n: np.linalg.norm(gt[n].center))
    s = scale_between(est, gt, scale_image)

    rows = []
    for name in shared:
        rows.append({
            "camera": name,
            "rotation_error_deg": rotation_error_deg(est[name].R, gt[name].R),
            "position_error": float(np.linalg.norm(est[name].center - s * gt[name].center)),
            "distance_from_reference": float(np.linalg.norm(est[name].center)),
        })
    rows.sort(key=lambda r: r["distance_from_reference"])

    errs = [r["rotation_error_deg"] for r in rows if r["camera"] != reference]
    pos = [r["position_error"] for r in rows if r["camera"] != reference]
    return {
        "scale": s,
        "scale_image": scale_image,
        "reference": reference,
        "n_cameras": len(shared),
        "mean_rotation_error_deg": float(np.mean(errs)) if errs else 0.0,
        "max_rotation_error_deg": float(np.max(errs)) if errs else 0.0,
        "mean_position_error": float(np.mean(pos)) if pos else 0.0,
        "cameras": rows,
    }


def rmse_reprojection(errors: np.ndarray) -> float:
    e = np.asarray(errors, dtype=float)
    e = e[np.isfinite(e)]
    return float(np.sqrt(np.mean(e**2))) if e.size else float("nan")
