"""An ``ImageStore`` over sfmkit's data directory, ``<root>/<dataset>/scene/``.

Images are named without extension, as sfmkit names them. Read-only.
"""

from __future__ import annotations

from pathlib import Path

from sfmview.domain import ImageNotFound, valid_name

EXTENSIONS = (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")


class FsImageStore:
    """The photos under ``root``."""

    def __init__(self, root) -> None:
        self.root = Path(root).resolve()

    def image_file(self, dataset: str, name: str) -> Path:
        if not (valid_name(dataset) and valid_name(name)):
            raise ImageNotFound(f"{dataset}/{name}")
        scene = self.root / dataset / "scene"
        # Resolved, so a case-insensitive disk does not find one file twice.
        found = {p.resolve() for p in (scene / f"{name}{ext}" for ext in EXTENSIONS)
                 if p.is_file()}
        if len(found) != 1:  # none, or two that could both be it
            raise ImageNotFound(f"{dataset}/{name}")
        (path,) = found
        if not path.is_relative_to(self.root):  # a symlink out of the root
            raise ImageNotFound(f"{dataset}/{name}")
        return path
