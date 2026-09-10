"""The `sfmkit colmap` command."""

from __future__ import annotations

import shutil
from pathlib import Path

from sfmkit.apps.cli._common import console, run_dir
from sfmkit.data import io
from sfmkit.data.colmap import read_model, run_colmap
from sfmkit.data.config import Config, load_config

FILES = ("cameras.txt", "images.txt", "points3D.txt")


def cmd_colmap(args) -> int:
    """The COLMAP model this run is scored against: copied, or computed."""
    cfg = load_config(args.config)
    run = run_dir(cfg, args.out)
    out = run / "colmap"

    if cfg.colmap.precomputed:
        extra = _precomputed(cfg, out)
    elif cfg.colmap.matches == "colmap":
        extra = _colmap_matches(cfg, out)
    elif cfg.colmap.matches == "sfmkit":
        console.print("[red]colmap.matches: sfmkit is not implemented yet[/red]")
        return 1
    else:
        console.print("[red]set `colmap.precomputed` or `colmap.matches`[/red]")
        return 1

    io.write_manifest(run, "colmap", cfg, config_path=args.config, extra=extra)
    return 0


def _precomputed(cfg: Config, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copyfile(Path(cfg.colmap.precomputed) / name, out / name)
    n = len(read_model(out)["poses"])
    console.print(f"using precomputed model from {cfg.colmap.precomputed}: {n} images")
    return {"source": "precomputed", "n_images": n}


def _colmap_matches(cfg: Config, out: Path) -> dict:
    images = cfg.sfm.images
    with console.status(f"COLMAP on {len(images)} images: features, matching, mapping"):
        s = run_colmap(cfg.scene_dir, images, out)
    console.print(f"registered [bold]{len(s.registered)}/{len(images)}[/bold] images, "
                  f"{s.n_points} points, {s.reprojection_error:.2f} px")
    if s.missing:
        console.print(f"[yellow]not registered:[/yellow] {', '.join(s.missing)}")
    return {"source": "colmap", "registered": s.registered, "missing": s.missing,
            "n_points": s.n_points, "reprojection_error": s.reprojection_error}
