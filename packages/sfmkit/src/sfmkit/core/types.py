"""Data structures for cameras, correspondences and reconstructions."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: The name of an image, as used to key matches, poses and observations.
ImageName = str

#: A position in an image's keypoint array.
KeypointIndex = int


@dataclass(frozen=True, eq=False)
class Pose:
    """A world-to-camera rigid transform: ``x_cam = R @ x_world + t``.

    COLMAP's convention, used unchanged throughout the package. ``R`` must be
    ``(3, 3)``; ``t`` must have three elements and is flattened to ``(3,)``.

    Construction checks shapes but not orthonormality, which costs roughly
    twenty times as much as building the object and would be paid tens of
    thousands of times per reconstruction. Call ``validate`` where the
    rotation comes from outside the library.
    """

    R: np.ndarray
    t: np.ndarray

    def __post_init__(self) -> None:
        R = np.asarray(self.R, dtype=float)
        if R.shape != (3, 3):
            raise ValueError(f"R must be (3, 3), got {R.shape}")
        t = np.asarray(self.t, dtype=float)
        if t.size != 3:
            raise ValueError(f"t must have 3 elements, got {t.shape}")
        object.__setattr__(self, "R", R)
        object.__setattr__(self, "t", t.reshape(3))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Pose):
            return NotImplemented
        return np.array_equal(self.R, other.R) and np.array_equal(self.t, other.t)

    def validate(self, tol: float = 1e-6) -> Pose:
        """Raise unless ``R`` is a proper rotation. Returns self, so it chains."""
        M = self.R @ self.R.T
        if np.abs(M - np.eye(3)).max() > tol:
            raise ValueError("R is not orthonormal")
        if self.R[0] @ np.cross(self.R[1], self.R[2]) < 0:
            raise ValueError("det(R) is -1: a reflection, not a rotation")
        return self

    @classmethod
    def identity(cls) -> Pose:
        return cls(np.eye(3), np.zeros(3))

    @property
    def center(self) -> np.ndarray:
        """Camera centre in world coordinates."""
        return -self.R.T @ self.t

    @property
    def matrix(self) -> np.ndarray:
        """The 4x4 homogeneous form."""
        T = np.eye(4)
        T[:3, :3] = self.R
        T[:3, 3] = self.t
        return T

    def inverse(self) -> Pose:
        return Pose(self.R.T, -self.R.T @ self.t)

    def compose(self, other: Pose) -> Pose:
        """``self ∘ other``: apply ``other`` first, then ``self``."""
        return Pose(self.R @ other.R, self.R @ other.t + self.t)

    def relative_to(self, ref: Pose) -> Pose:
        """This pose expressed in ``ref``'s camera frame."""
        return self.compose(ref.inverse())

    def transform(self, points: np.ndarray) -> np.ndarray:
        """Map world points ``(N, 3)`` into this camera's frame."""
        return np.asarray(points, dtype=float) @ self.R.T + self.t

    def projection_matrix(self, K: np.ndarray) -> np.ndarray:
        """The 3x4 matrix ``K [R | t]``."""
        return np.asarray(K, dtype=float) @ np.hstack([self.R, self.t[:, None]])


@dataclass(eq=False)
class Matches:
    """Putative or verified correspondences between two images.

    ``pairs`` holds indices into ``keypoints0`` / ``keypoints1``; ``inliers`` is
    a boolean mask over ``pairs``, set once geometric verification has run.
    """

    image0: ImageName
    image1: ImageName
    keypoints0: np.ndarray  # (N0, 2)
    keypoints1: np.ndarray  # (N1, 2)
    pairs: np.ndarray  # (M, 2) int
    scores: np.ndarray | None = None
    inliers: np.ndarray | None = None  # (M,) bool

    def __post_init__(self) -> None:
        pairs = np.asarray(self.pairs)
        if pairs.ndim != 2 or pairs.shape[1] != 2:
            raise ValueError(f"pairs must be (M, 2), got {pairs.shape}")
        for name in ("scores", "inliers"):
            v = getattr(self, name)
            if v is not None and len(v) != len(pairs):
                raise ValueError(
                    f"{name} has {len(v)} entries but there are {len(pairs)} pairs"
                )

    @property
    def n_matches(self) -> int:
        return len(self.pairs)

    @property
    def n_inliers(self) -> int:
        return int(self.pairs.shape[0] if self.inliers is None else self.inliers.sum())

    @property
    def inlier_ratio(self) -> float:
        return self.n_inliers / self.n_matches if self.n_matches else 0.0

    def verified_pairs(self) -> np.ndarray:
        """The ``(M', 2)`` index pairs that survived verification."""
        return self.pairs if self.inliers is None else self.pairs[self.inliers]

    def points(self) -> tuple[np.ndarray, np.ndarray]:
        """Verified correspondences as two ``(M', 2)`` coordinate arrays."""
        p = self.verified_pairs()
        return self.keypoints0[p[:, 0]], self.keypoints1[p[:, 1]]


@dataclass
class Track:
    """One 3D point, and every image observation that belongs to it.

    ``observations`` maps image name to keypoint index. A track with two
    observations in the same image is contradictory and is rejected during
    construction -- a single 3D point cannot project to two places in one photo.
    """

    observations: dict[ImageName, KeypointIndex] = field(default_factory=dict)

    @property
    def length(self) -> int:
        return len(self.observations)

    def images(self) -> set[ImageName]:
        return set(self.observations)


@dataclass(eq=False)
class Reconstruction:
    """Cameras, 3D points and their observations.

    ``points`` is ``(N, 3)`` and indexed by track id, so ``tracks[i]`` describes
    where ``points[i]`` was seen. Entries are NaN until a track is triangulated.
    """

    K: np.ndarray
    poses: dict[ImageName, Pose] = field(default_factory=dict)
    points: np.ndarray = field(default_factory=lambda: np.zeros((0, 3)))
    tracks: list[Track] = field(default_factory=list)

    @property
    def registered(self) -> list[ImageName]:
        return list(self.poses)

    @property
    def n_points(self) -> int:
        return int(np.isfinite(self.points).all(axis=1).sum())

    def triangulated_mask(self) -> np.ndarray:
        """Which tracks currently have a valid 3D position."""
        if len(self.points) == 0:
            return np.zeros(0, dtype=bool)
        return np.isfinite(self.points).all(axis=1)

    def observations_of(self, image: ImageName) -> tuple[np.ndarray, np.ndarray]:
        """Triangulated track ids visible in ``image``, and their keypoint indices."""
        ok = self.triangulated_mask()
        tid, kid = [], []
        for i, tr in enumerate(self.tracks):
            if ok[i] and image in tr.observations:
                tid.append(i)
                kid.append(tr.observations[image])
        return np.asarray(tid, dtype=np.intp), np.asarray(kid, dtype=np.intp)

    def relative_poses(self, reference: ImageName) -> dict[ImageName, Pose]:
        """All poses re-expressed in ``reference``'s frame."""
        ref = self.poses[reference]
        return {n: p.relative_to(ref) for n, p in self.poses.items()}
