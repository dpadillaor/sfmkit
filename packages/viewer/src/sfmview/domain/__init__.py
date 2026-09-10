"""What the viewer shows, as plain values, and the geometry that relates them.

No I/O, no HTTP, no broker: everything here is tested with arrays alone.
"""

from sfmview.domain.frames import assemble_scene, camera_frame, shared_frame
from sfmview.domain.model import (
    Camera,
    Model,
    RunId,
    RunNotFound,
    RunSummary,
    Scene,
)

__all__ = [
    "Camera", "Model", "RunId", "RunNotFound", "RunSummary", "Scene",
    "assemble_scene", "camera_frame", "shared_frame",
]
