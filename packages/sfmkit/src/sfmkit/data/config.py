"""Experiment configuration, loaded from YAML.

A config lives inside the project it belongs to::

    projects/valencia/
    |-- data/        the photographs, and anything precomputed
    |-- configs/     one YAML an experiment
    `-- runs/        what a run writes, and the frozen reference-* runs

so the project is the directory the config sits in and nothing names it twice.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import yaml

from sfmkit.core.localize import REFINEMENTS
from sfmkit.core.reconstruct import BUNDLE_SOLVERS
from sfmkit.data.features import DEVICES

__all__ = [
    "CalibrateConfig", "ColmapConfig", "Config", "DenseConfig", "LocalizeConfig", "SfmConfig",
    "default_run_dir", "load_config", "project_dir",
]


@dataclass
class CalibrateConfig:
    """Where the intrinsics come from: chessboard photos, a precomputed K, or
    the scene photos' EXIF. One of them."""

    images: str = ""  # glob of chessboard photos
    pattern: list[int] = field(default_factory=lambda: [9, 6])  # inner corners
    intrinsics: str = ""  # precomputed 3x3 K, used when there are no photos
    exif: bool = False  # K from the scene photos' 35 mm equivalent focal length
    sensor_aspect: list[int] = field(default_factory=lambda: [4, 3])  # of the whole sensor

    def __post_init__(self) -> None:
        sources = [n for n, v in (("images", self.images), ("intrinsics", self.intrinsics),
                                  ("exif", self.exif)) if v]
        if len(sources) > 1:
            raise ValueError(f"calibrate takes one source, not {' and '.join(sources)}")
        if len(self.sensor_aspect) != 2 or min(self.sensor_aspect) <= 0:
            raise ValueError("calibrate.sensor_aspect is two positive numbers, e.g. [4, 3]")


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
    bundle_solver: str = "schur"  # schur | scipy: the same problem, scipy's slower

    def __post_init__(self) -> None:
        if self.device not in DEVICES:
            raise ValueError(f"sfm.device must be one of {DEVICES}, not {self.device!r}")
        if self.bundle_solver not in BUNDLE_SOLVERS:
            raise ValueError(f"sfm.bundle_solver must be one of {tuple(BUNDLE_SOLVERS)}, "
                             f"not {self.bundle_solver!r}")


@dataclass
class LocalizeConfig:
    """The image to localise, kept out of the reconstruction itself."""

    query: str | None = None
    refine: str = "camera"  # after RANSAC: none | pose | camera (K too, if estimated)

    def __post_init__(self) -> None:
        if self.refine not in REFINEMENTS:
            raise ValueError(f"localize.refine must be one of {REFINEMENTS}, "
                             f"not {self.refine!r}")


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
class DenseConfig:
    """COLMAP's dense reconstruction of the colmap stage's model. Needs CUDA."""

    enabled: bool = False
    max_image_size: int = 2000  # images are downscaled to this size for stereo

    def __post_init__(self) -> None:
        if self.max_image_size <= 0:
            raise ValueError(f"dense.max_image_size must be positive, not {self.max_image_size}")


@dataclass
class Config:
    """One experiment over one project.

    Neither ``dataset`` nor ``dataset_dir`` is read from the YAML: both come
    from where the config file sits.
    """

    dataset: str
    name: str = ""
    seed: int = 0
    calibrate: CalibrateConfig = field(default_factory=CalibrateConfig)
    sfm: SfmConfig = field(default_factory=SfmConfig)
    localize: LocalizeConfig = field(default_factory=LocalizeConfig)
    colmap: ColmapConfig = field(default_factory=ColmapConfig)
    dense: DenseConfig = field(default_factory=DenseConfig)
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
    "dense": DenseConfig,
}

#: Paths inside a section, resolved against the dataset directory.
PATH_FIELDS = {"calibrate": ("images", "intrinsics"), "colmap": ("precomputed",)}


def project_dir(config_path) -> Path:
    """The project a config belongs to: whatever holds its ``configs/``."""
    config_path = Path(config_path).resolve()
    if config_path.parent.name != "configs":
        raise ValueError(
            f"{config_path}: a config belongs in <project>/configs/, beside the "
            "project's data/ and runs/, so that the project is where it sits"
        )
    return config_path.parent.parent


def default_run_dir(cfg: Config) -> Path:
    return Path(cfg.dataset_dir).parent / "runs" / cfg.name


def _section(cls, raw, where: str):
    raw = raw or {}
    unknown = set(raw) - {f.name for f in fields(cls)}
    if unknown:
        raise ValueError(f"unknown keys in {where}: {sorted(unknown)}")
    return cls(**raw)


def load_config(path) -> Config:
    """Load a YAML config, rejecting unknown keys rather than ignoring them.

    Relative paths are resolved against the project's ``data/``, so a project
    copied or mounted elsewhere works unchanged.
    """
    path = Path(path)
    raw = yaml.safe_load(path.read_text()) or {}
    top = {"name", "seed", *SECTIONS}
    unknown = set(raw) - top
    if unknown:
        extra = ". `dataset` is the project's directory now" if "dataset" in unknown else ""
        raise ValueError(f"unknown config keys: {sorted(unknown)}{extra}")

    project = project_dir(path)
    dataset_dir = project / "data"
    for key, fieldnames in PATH_FIELDS.items():
        section = raw.get(key) or {}
        for f in fieldnames:
            value = section.get(f)
            if value and not Path(value).is_absolute():
                section[f] = str(dataset_dir / value)
        raw[key] = section

    return Config(
        dataset=project.name,
        name=raw.get("name") or path.stem,
        seed=raw.get("seed", 0),
        dataset_dir=str(dataset_dir),
        **{k: _section(cls, raw.get(k), k) for k, cls in SECTIONS.items()},
    )
