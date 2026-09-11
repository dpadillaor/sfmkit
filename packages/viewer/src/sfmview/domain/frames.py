"""Bringing two reconstructions into one frame.

A reconstruction is known up to a similarity: where the world is, how it is
turned, how big it is. sfmkit's ``evaluate`` fixes that by expressing both
models in one camera's frame (the reference) and scaling by one camera's
distance from it; the viewer does the same, so what it draws is what is scored.
The shared frame is sfmkit's, at sfmkit's scale.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from sfmview.domain.model import Camera, Model, RunId, Scene


def camera_frame(camera: Camera, scale: float = 1.0) -> np.ndarray:
    """The 4x4 that takes world points into ``camera``'s frame, times ``scale``."""
    T = np.eye(4)
    T[:3, :3] = scale * camera.R
    T[:3, 3] = scale * camera.t
    return T


def _apply(T: np.ndarray, point: np.ndarray) -> np.ndarray:
    return T[:3, :3] @ point + T[:3, 3]


def shared_frame(ours: Model, theirs: Model, reference: str,
                 scale_image: str | None = None) -> tuple[np.ndarray, np.ndarray]:
    """The similarities that bring ``ours`` and ``theirs`` into ``reference``'s
    frame, at our scale.

    ``scale_image`` names the camera whose distance from the reference fixes
    the scale; by default, or when it is not in both, the one farthest from it
    in ``theirs``, as sfmkit's evaluate picks it. With no second camera in
    common the scale stays 1.
    """
    a, b = ours.camera(reference), theirs.camera(reference)
    if a is None or b is None:
        raise ValueError(f"reference {reference!r} is not in both models")
    T_ours, T_theirs = camera_frame(a), camera_frame(b)

    shared = [c.name for c in ours.cameras
              if not c.query and c.name != reference and theirs.camera(c.name) is not None]
    if scale_image not in shared:
        scale_image = None  # named, but not in both: pick as evaluate would
    if scale_image is None and shared:
        scale_image = max(shared, key=lambda n: np.linalg.norm(
            _apply(T_theirs, theirs.camera(n).center)))
    if scale_image is None:
        return T_ours, T_theirs

    d_ours = np.linalg.norm(_apply(T_ours, ours.camera(scale_image).center))
    d_theirs = np.linalg.norm(_apply(T_theirs, theirs.camera(scale_image).center))
    if d_theirs < 1e-12:
        return T_ours, T_theirs
    return T_ours, camera_frame(b, d_ours / d_theirs)


def assemble_scene(run: RunId, ours: Model | None, theirs: Model | None, *,
                   reference: str | None = None, scale_image: str | None = None,
                   dense: bool = False) -> Scene:
    """A run's scene, its models in one frame when they can be.

    The dense cloud is COLMAP's and lives in its frame, so it takes ``theirs``'s
    similarity. When the models share no reference each stays in its own frame
    and they are drawn apart.
    """
    if reference is None and ours is not None and ours.cameras:
        reference = next((c.name for c in ours.cameras if not c.query), None)

    models = [m for m in (ours, theirs) if m is not None]
    if ours is not None and theirs is not None and reference is not None:
        try:
            T_ours, T_theirs = shared_frame(ours, theirs, reference, scale_image)
            models = [replace(ours, to_common=T_ours), replace(theirs, to_common=T_theirs)]
        except ValueError:
            pass
    elif len(models) == 1 and reference is not None and models[0].camera(reference):
        models = [replace(models[0], to_common=camera_frame(models[0].camera(reference)))]

    colmap = next((m for m in models if m.source == "colmap"), None)
    dense_T = None if not dense or colmap is None else colmap.to_common
    return Scene(run, tuple(models), reference, dense_T)

