"""A Structure-from-Motion library.

Two-view geometry, robust estimation, feature tracks, incremental
reconstruction, bundle adjustment and visual localisation.

Points are row-major -- 3D ``(N, 3)``, image ``(N, 2)`` -- and poses are
world-to-camera as in COLMAP. See :doc:`docs/architecture` for the package
layout and the conventions it enforces."""

from sfmkit.core.types import Matches, Pose, Reconstruction, Track

__all__ = ["Matches", "Pose", "Reconstruction", "Track"]
__version__ = "0.1.0"
