"""Shared pieces for the CLI commands: the console, progress bars and helpers."""

from __future__ import annotations

import itertools

import numpy as np
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from sfmkit.data.config import Config

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


def pairs_of(cfg: Config) -> list[tuple[str, str]]:
    """Which image pairs to match: all of them, or only those touching the reference."""
    names = cfg.image_names
    if cfg.exhaustive:
        return list(itertools.combinations(names, 2))
    ref = cfg.reference or names[0]
    return [(ref, n) for n in names if n != ref]
