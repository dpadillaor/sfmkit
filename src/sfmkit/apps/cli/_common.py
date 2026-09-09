"""Shared pieces for the CLI commands.

One entry point, one subcommand per pipeline stage. Stage order lives in the
Makefile and in the config, not in module names, so inserting a stage does not
rename anything.

Each stage reads an explicit input directory and writes an explicit output
directory, and every output carries a manifest. That contract is the fix for the
original pipeline's real defect: there, stages found their inputs through
hardcoded relative paths, results were never saved at all, and a missing file
was patched by pasting numbers into the next script's source.
"""

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
