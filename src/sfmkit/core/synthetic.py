"""Synthetic scenes with known ground truth.

The point of this module is that the whole library can be tested without a
single photograph: cameras and 3D points are generated, projected, and the
resulting matches fed back through the pipeline, so any test can assert against
the exact answer rather than against a previous run.

It also makes track construction testable, which is otherwise awkward: here we
know by construction which keypoints across which images are the same 3D point.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from sfmkit.core.geometry import project
from sfmkit.core.types import Matches, Pose

__all__ = ["SyntheticScene", "make_scene"]


@dataclass
class SyntheticScene:
    K: np.ndarray
    images: list[str]
    poses: dict[str, Pose]  # ground truth, world-to-camera
    points: np.ndarray  # (N, 3) ground truth
    keypoints: dict[str, np.ndarray]  # image -> (M, 2) observed pixels
    visible: dict[str, np.ndarray]  # image -> point index for each keypoint
    image_size: tuple[int, int]

    def matches_for(self, a: str, b: str, *, noise: float = 0.0,
                    outlier_ratio: float = 0.0, seed: int = 0) -> Matches:
        """Build the correspondences two images share, optionally corrupted."""
        rng = np.random.default_rng(seed)
        ia, ib = self.visible[a], self.visible[b]
        common = np.intersect1d(ia, ib)
        pos_a = {p: k for k, p in enumerate(ia)}
        pos_b = {p: k for k, p in enumerate(ib)}
        pairs = np.array([[pos_a[p], pos_b[p]] for p in common], dtype=np.intp)

        kp_a = self.keypoints[a].copy()
        kp_b = self.keypoints[b].copy()
        if noise > 0:
            kp_a += rng.normal(0, noise, kp_a.shape)
            kp_b += rng.normal(0, noise, kp_b.shape)

        if outlier_ratio > 0 and len(pairs):
            n_bad = int(round(outlier_ratio * len(pairs)))
            bad = rng.choice(len(pairs), n_bad, replace=False)
            # Repoint a fraction of the matches at unrelated keypoints.
            pairs[bad, 1] = rng.integers(0, len(kp_b), n_bad)

        return Matches(image0=a, image1=b, keypoints0=kp_a, keypoints1=kp_b, pairs=pairs)

    def true_relative(self, name: str, reference: str) -> Pose:
        return self.poses[name].relative_to(self.poses[reference])


def make_scene(
    n_cameras: int = 5,
    n_points: int = 300,
    *,
    image_size: tuple[int, int] = (1600, 1200),
    focal: float = 1400.0,
    seed: int = 0,
    visibility: float = 0.8,
) -> SyntheticScene:
    """A wall of 3D points viewed by cameras spread along an arc facing it.

    The arc gives genuine parallax between every pair of cameras, so tracks
    spanning several images are both possible and useful -- the situation the
    star-shaped graph could not exploit.
    """
    rng = np.random.default_rng(seed)
    w, h = image_size
    K = np.array([[focal, 0.0, w / 2.0], [0.0, focal, h / 2.0], [0.0, 0.0, 1.0]])

    # Points on a rough facade at z ~ 10, with depth relief.
    points = np.column_stack([
        rng.uniform(-4.0, 4.0, n_points),
        rng.uniform(-3.0, 3.0, n_points),
        rng.uniform(9.0, 12.0, n_points),
    ])

    images = [f"cam{i:02d}" for i in range(n_cameras)]
    poses: dict[str, Pose] = {}
    for i, name in enumerate(images):
        # Cameras on an arc, all looking at the centre of the facade.
        angle = np.deg2rad(np.linspace(-25, 25, n_cameras)[i]) if n_cameras > 1 else 0.0
        radius = 3.0
        centre = np.array([radius * np.sin(angle), rng.uniform(-0.2, 0.2), -radius * np.cos(angle)])
        forward = np.array([0.0, 0.0, 10.0]) - centre
        forward /= np.linalg.norm(forward)
        right = np.cross([0.0, 1.0, 0.0], forward)
        right /= np.linalg.norm(right)
        up = np.cross(forward, right)
        R = np.vstack([right, up, forward])  # world -> camera
        poses[name] = Pose(R, -R @ centre)

    keypoints: dict[str, np.ndarray] = {}
    visible: dict[str, np.ndarray] = {}
    for name in images:
        uv = project(points, K, poses[name])
        inside = (
            np.isfinite(uv).all(axis=1)
            & (uv[:, 0] >= 0) & (uv[:, 0] < w)
            & (uv[:, 1] >= 0) & (uv[:, 1] < h)
        )
        keep = inside & (rng.random(n_points) < visibility)
        idx = np.flatnonzero(keep)
        keypoints[name] = uv[idx]
        visible[name] = idx

    return SyntheticScene(K, images, poses, points, keypoints, visible, image_size)
