"""Experiment configuration, loaded from YAML."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import yaml

from sfmkit.data.features import DEVICES

__all__ = [
    "CalibrateConfig", "ColmapConfig", "Config", "LocalizeConfig", "SfmConfig",
    "data_root", "default_run_dir", "load_config", "runs_root",
]


@dataclass
class CalibrateConfig:
    """Where the intrinsics come from: chessboard photos, or a precomputed K."""

    images: str = ""  # glob of chessboard photos
    pattern: list[int] = field(default_factory=lambda: [9, 6])  # inner corners
    intrinsics: str = ""  # precomputed 3x3 K, used when there are no photos


@dataclass
class SfmConfig:
    """Matching, verification and reconstruction.

    ``reference`` is the camera the reconstruction is anchored to and that all
    comparisons align against.
    """

    images: list[str] = field(default_factory=list)
    reference: str | None = None

    # matching
    max_keypoints: int = 2048
    exhaustive: bool = True  # all pairs, rather than only reference pairs
    device: str = "auto"  # auto | cpu | cuda; CPU and GPU give slightly different matches

    # verification
    ransac_threshold: float = 4.0
    ransac_iterations: int = 1000
    min_inliers: int = 20

    # reconstruction
    min_track_length: int = 2
    min_triangulation_angle_deg: float = 1.0
    max_reprojection_error: float = 8.0
    pnp_threshold: float = 8.0
    min_pnp_correspondences: int = 12

    def __post_init__(self) -> None:
        if self.device not in DEVICES:
            raise ValueError(f"sfm.device must be one of {DEVICES}, not {self.device!r}")


@dataclass
class LocalizeConfig:
    """The image to localise, kept out of the reconstruction itself."""

    query: str | None = None


COLMAP_MATCHES = ("colmap", "sfmkit")
COLMAP_CAMERAS = ("self", "fixed")


@dataclass
class ColmapConfig:
    """The COLMAP model the run is scored against: copied, or computed.

    ``precomputed`` copies a model directory. Otherwise COLMAP runs, and
    ``matches`` says whose keypoints and matches it reconstructs from: its own
    (``colmap``) or those of ``verify`` (``sfmkit``). ``camera`` says whether it
    calibrates the camera itself (``self``) or takes the K from ``calibrate``
    (``fixed``); the query always gets a camera of its own, calibrated by COLMAP.
    """

    precomputed: str = ""
    matches: str = ""
    camera: str = "self"

    def __post_init__(self) -> None:
        if self.precomputed and self.matches:
            raise ValueError("set either colmap.precomputed or colmap.matches, not both")
        if self.matches and self.matches not in COLMAP_MATCHES:
            raise ValueError(
                f"colmap.matches must be one of {COLMAP_MATCHES}, not {self.matches!r}")
        if self.camera not in COLMAP_CAMERAS:
            raise ValueError(
                f"colmap.camera must be one of {COLMAP_CAMERAS}, not {self.camera!r}")
        if self.precomputed and self.camera != "self":
            raise ValueError("colmap.camera applies when COLMAP runs, not to a precomputed model")


@dataclass
class Config:
    """One experiment over one dataset.

    ``dataset_dir`` is not read from the YAML: ``load_config`` fills it in from
    ``dataset`` and the data root.
    """

    dataset: str
    name: str = ""
    seed: int = 0
    calibrate: CalibrateConfig = field(default_factory=CalibrateConfig)
    sfm: SfmConfig = field(default_factory=SfmConfig)
    localize: LocalizeConfig = field(default_factory=LocalizeConfig)
    colmap: ColmapConfig = field(default_factory=ColmapConfig)
    dataset_dir: str = ""

    @property
    def scene_dir(self) -> Path:
        return Path(self.dataset_dir) / "scene"

    def to_dict(self) -> dict:
        return asdict(self)


SECTIONS = {
    "calibrate": CalibrateConfig,
    "sfm": SfmConfig,
    "localize": LocalizeConfig,
    "colmap": ColmapConfig,
}

#: Paths inside a section, resolved against the dataset directory.
PATH_FIELDS = {"calibrate": ("images", "intrinsics"), "colmap": ("precomputed",)}


def data_root() -> Path:
    """Where datasets live: ``$SFMKIT_DATA``, or ``data`` in the working directory."""
    return Path(os.environ.get("SFMKIT_DATA", "data"))


def runs_root() -> Path:
    """Where runs are written: ``$SFMKIT_RUNS``, or ``runs`` in the working directory."""
    return Path(os.environ.get("SFMKIT_RUNS", "runs"))


def default_run_dir(cfg: Config) -> Path:
    return runs_root() / cfg.dataset / cfg.name


def _section(cls, raw, where: str):
    raw = raw or {}
    unknown = set(raw) - {f.name for f in fields(cls)}
    if unknown:
        raise ValueError(f"unknown keys in {where}: {sorted(unknown)}")
    return cls(**raw)


def load_config(path) -> Config:
    """Load a YAML config, rejecting unknown keys rather than ignoring them.

    Relative paths are resolved against the dataset directory, so the same
    config works wherever the data root is mounted.
    """
    path = Path(path)
    raw = yaml.safe_load(path.read_text()) or {}
    top = {"dataset", "name", "seed", *SECTIONS}
    unknown = set(raw) - top
    if unknown:
        raise ValueError(f"unknown config keys: {sorted(unknown)}")
    if not raw.get("dataset"):
        raise ValueError(f"{path}: `dataset` is required")

    dataset_dir = (data_root() / raw["dataset"]).resolve()
    for key, fieldnames in PATH_FIELDS.items():
        section = raw.get(key) or {}
        for f in fieldnames:
            value = section.get(f)
            if value and not Path(value).is_absolute():
                section[f] = str(dataset_dir / value)
        raw[key] = section

    return Config(
        dataset=raw["dataset"],
        name=raw.get("name") or path.stem,
        seed=raw.get("seed", 0),
        dataset_dir=str(dataset_dir),
        **{k: _section(cls, raw.get(k), k) for k, cls in SECTIONS.items()},
    )
