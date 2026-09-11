"""What a photo's EXIF says about the camera that took it."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

__all__ = ["CameraExif", "read_camera"]

_EXIF_IFD = 0x8769
_MODEL = 0x0110
_FOCAL_MM = 0x920A
_FOCAL_35MM = 0xA405


@dataclass(frozen=True)
class CameraExif:
    model: str | None
    focal_mm: float | None
    focal_35mm: float
    size: tuple[int, int]  # width, height in pixels, as stored


def read_camera(path) -> CameraExif:
    """The camera settings in ``path``'s EXIF. Raises ``ValueError`` when the
    35 mm equivalent focal length, the one needed, is not there."""
    path = Path(path)
    with Image.open(path) as im:
        exif = im.getexif()
        ifd = exif.get_ifd(_EXIF_IFD)
        size = im.size
    focal_35mm = ifd.get(_FOCAL_35MM)
    if not focal_35mm:
        raise ValueError(f"{path.name} has no 35 mm equivalent focal length in its EXIF")
    focal = ifd.get(_FOCAL_MM)
    model = exif.get(_MODEL)
    return CameraExif(model=str(model).strip() if model else None,
                      focal_mm=float(focal) if focal else None,
                      focal_35mm=float(focal_35mm), size=size)
