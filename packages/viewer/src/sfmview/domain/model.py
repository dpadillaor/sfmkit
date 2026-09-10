"""Runs, and the reconstructions a run holds."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np

# One path component, never "." or "..": a run is named by its project and its
# config, and the names reach the filesystem.
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class RunNotFound(LookupError):
    """No run by that name, or not the part of it asked for."""


@dataclass(frozen=True)
class RunId:
    """A run, as sfmkit lays them out: ``runs/<project>/<config>/``."""

    project: str
    config: str

    def __post_init__(self) -> None:
        for part in (self.project, self.config):
            if not _NAME.fullmatch(part):
                raise ValueError(f"not a run name: {part!r}")

    def __str__(self) -> str:
        return f"{self.project}/{self.config}"


@dataclass(frozen=True)
class RunSummary:
    """What a run list shows: which stages ran, and how well."""

    run: RunId
    stages: tuple[str, ...]
    updated: str | None  # the latest manifest's timestamp
    metrics: Mapping[str, float | None]
    layers: tuple[str, ...]  # what can be drawn: "sfmkit", "colmap", "dense"


@dataclass(frozen=True, eq=False)
class Camera:
    """A posed camera. ``R`` and ``t`` take world points into the camera's frame,
    OpenCV's axes: x right, y down, z forward."""

    name: str
    R: np.ndarray
    t: np.ndarray
    K: np.ndarray | None = None
    size: tuple[int, int] | None = None  # width, height in pixels
    query: bool = False  # the photo placed afterwards, not reconstructed with the rest

    @property
    def center(self) -> np.ndarray:
        return -self.R.T @ self.t


@dataclass(frozen=True, eq=False)
class Model:
    """One reconstruction: its cameras and points, in its own frame, and the
    similarity that brings it into the scene's shared frame."""

    source: str  # "sfmkit" or "colmap"
    cameras: tuple[Camera, ...]
    points: np.ndarray  # (N, 3)
    colors: np.ndarray | None = None  # (N, 3) uint8
    to_common: np.ndarray = field(default_factory=lambda: np.eye(4))

    def camera(self, name: str) -> Camera | None:
        return next((c for c in self.cameras if c.name == name), None)


@dataclass(frozen=True, eq=False)
class Scene:
    """Everything a run can draw, the models brought into one frame."""

    run: RunId
    models: tuple[Model, ...]
    reference: str | None  # the camera whose frame is shared
    dense_to_common: np.ndarray | None = None  # the dense cloud's similarity, if there is one
