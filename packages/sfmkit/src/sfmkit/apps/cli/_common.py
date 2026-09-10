"""Shared pieces for the CLI commands: the console, progress bars and helpers."""

from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from sfmkit.data.config import Config, default_run_dir

console = Console()


def progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    )


def load_K(path) -> np.ndarray:
    return np.loadtxt(path).reshape(3, 3)


def run_dir(cfg: Config, out: str | None) -> Path:
    """``--out`` if given, otherwise ``runs/<dataset>/<config>``."""
    return Path(out) if out else default_run_dir(cfg)


def pairs_of(cfg: Config) -> list[tuple[str, str]]:
    """Which image pairs to match: all of them, or only those touching the reference."""
    names = cfg.sfm.images
    if cfg.sfm.exhaustive:
        return list(itertools.combinations(names, 2))
    ref = cfg.sfm.reference or names[0]
    return [(ref, n) for n in names if n != ref]
