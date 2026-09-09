"""A small Structure-from-Motion library.

Conventions used throughout, chosen once and enforced at module boundaries:

* **Point arrays are row-major**: 3D points are ``(N, 3)``, image points ``(N, 2)``.
  Functions that need column-major internally transpose locally; they never
  return column-major arrays. (The original code mixed the two freely, which was
  a recurring source of confusion.)
* **Poses are world-to-camera**, matching COLMAP: ``x_cam = R @ x_world + t``.
* **Nothing in this package performs I/O or reads configuration.** Callers pass
  arrays in and get arrays back. Only ``sfmkit.io`` touches the filesystem.
* **Randomness is always an explicit ``seed`` argument.** There is no implicit
  global RNG anywhere.
"""

from sfmkit.core.types import Matches, Pose, Reconstruction, Track

__all__ = ["Matches", "Pose", "Reconstruction", "Track"]
__version__ = "0.1.0"
