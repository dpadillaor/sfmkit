"""Detect what has changed between two photographs of the same place."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

__all__ = ["ChangeMap", "align_by_homography", "detect_changes"]


@dataclass
class ChangeMap:
    warped: np.ndarray  # the historical image, aligned to the modern one
    mask: np.ndarray  # bool, True where the scene appears to have changed
    score: np.ndarray  # float32 dissimilarity in [0, 1], before thresholding
    homography: np.ndarray
    n_inliers: int
    changed_fraction: float


def align_by_homography(
    src_points: np.ndarray,
    dst_points: np.ndarray,
    *,
    threshold: float = 5.0,
    seed: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Homography mapping ``src_points`` onto ``dst_points``, with an inlier mask."""
    if seed is not None:
        cv2.setRNGSeed(int(seed))
    H, mask = cv2.findHomography(
        np.asarray(src_points, dtype=np.float64).reshape(-1, 1, 2),
        np.asarray(dst_points, dtype=np.float64).reshape(-1, 1, 2),
        cv2.RANSAC, threshold, maxIters=5000, confidence=0.999,
    )
    if H is None:
        raise ValueError("could not estimate a homography from these correspondences")
    return H, (mask.ravel().astype(bool) if mask is not None else np.ones(len(src_points), bool))


def _structure(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Local gradient orientation and a contrast-normalised intensity.

    Both are invariant to the global brightness and contrast differences that
    dominate any comparison between a modern photograph and a historical plate.
    """
    g = image.astype(np.float32)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    orientation = np.arctan2(gy, gx)
    magnitude = np.sqrt(gx**2 + gy**2)

    blur = cv2.GaussianBlur(g, (0, 0), 9)
    local_sd = np.sqrt(np.maximum(cv2.GaussianBlur(g**2, (0, 0), 9) - blur**2, 1e-6))
    normalised = (g - blur) / (local_sd + 1e-3)
    return np.stack([orientation, magnitude], axis=-1), normalised


def detect_changes(
    historical: np.ndarray,
    modern: np.ndarray,
    src_points: np.ndarray,
    dst_points: np.ndarray,
    *,
    threshold: float = 0.38,
    min_area: int = 120,
    seed: int | None = None,
) -> ChangeMap:
    """Align one image onto the other and flag the regions that differ.

    Comparison uses local structure -- gradient orientation and contrast-
    normalised intensity -- rather than raw brightness, so that differences in
    exposure and tone are not reported as change.

    Parameters
    ----------
    historical, modern
        The two images. ``historical`` is warped onto ``modern``.
    src_points, dst_points
        Verified correspondences between them, in that order.
    threshold
        Applied to a dissimilarity in [0, 1]. There is no ground truth for
        "changed", so this is a calibration choice: raise it for only the
        strongest structural differences, lower it to catch subtler ones along
        with more false positives.
    min_area
        Connected components smaller than this many pixels are discarded,
        removing the speckle that survives thresholding.

    Notes
    -----
    A homography is exact only for a plane or a pure rotation, so a facade
    aligns well while objects at very different depths do not; misalignment
    there appears as change.
    """
    H, inliers = align_by_homography(src_points, dst_points, seed=seed)
    h, w = modern.shape[:2]

    hist_grey = historical if historical.ndim == 2 else cv2.cvtColor(historical, cv2.COLOR_BGR2GRAY)
    mod_grey = modern if modern.ndim == 2 else cv2.cvtColor(modern, cv2.COLOR_BGR2GRAY)

    warped = cv2.warpPerspective(hist_grey, H, (w, h))
    valid = cv2.warpPerspective(np.ones_like(hist_grey, dtype=np.uint8), H, (w, h)) > 0

    struct_a, norm_a = _structure(warped)
    struct_b, norm_b = _structure(mod_grey)

    # Orientation difference, weighted by how much gradient there is to compare.
    d_theta = np.abs(np.angle(np.exp(1j * (struct_a[..., 0] - struct_b[..., 0])))) / np.pi
    weight = np.minimum(struct_a[..., 1], struct_b[..., 1])
    weight = weight / (np.percentile(weight[valid], 95) + 1e-6)
    weight = np.clip(weight, 0.0, 1.0)

    d_intensity = np.abs(norm_a - norm_b)
    d_intensity = d_intensity / (np.percentile(d_intensity[valid], 95) + 1e-6)

    score = np.clip(0.5 * d_theta * weight + 0.5 * np.clip(d_intensity, 0, 1), 0, 1)
    score = cv2.GaussianBlur(score.astype(np.float32), (0, 0), 3)
    score[~valid] = 0.0

    mask = (score > threshold).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    cleaned = np.zeros_like(mask, dtype=bool)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            cleaned |= labels == i

    return ChangeMap(
        warped=warped,
        mask=cleaned,
        score=score,
        homography=H,
        n_inliers=int(inliers.sum()),
        changed_fraction=float(cleaned.sum() / max(valid.sum(), 1)),
    )
