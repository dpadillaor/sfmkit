"""Experiment configuration, loaded from YAML."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import yaml

__all__ = ["Config", "load_config"]


@dataclass
class Config:
    name: str = "default"
    images_dir: str = ""
    image_names: list[str] = field(default_factory=list)
    reference: str | None = None
    query: str | None = None  # the image to localise (e.g. the historical photo)
    intrinsics: str = ""  # path to a 3x3 K matrix
    seed: int = 0

    # matching
    max_keypoints: int = 2048
    exhaustive: bool = True  # all pairs, rather than only reference pairs

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

    # evaluation
    colmap_model: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def load_config(path) -> Config:
    """Load a YAML config, rejecting unknown keys rather than ignoring them."""
    raw = yaml.safe_load(Path(path).read_text()) or {}
    known = {f.name for f in fields(Config)}
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f"unknown config keys: {sorted(unknown)}")
    return Config(**raw)
