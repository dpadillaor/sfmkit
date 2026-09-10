"""The `sfmkit colmap` command."""

from __future__ import annotations

import shutil
from pathlib import Path

from sfmkit.apps.cli._common import console, load_K, run_dir
from sfmkit.data import io
from sfmkit.data.colmap import ColmapSummary, read_model, run_colmap, run_colmap_on_matches
from sfmkit.data.config import Config, load_config

FILES = ("cameras.txt", "images.txt", "points3D.txt")


def cmd_colmap(args) -> int:
    """The COLMAP model this run is scored against: copied, or computed."""
    cfg = load_config(args.config)
    run = run_dir(cfg, args.out)
    out = run / "colmap"

    if cfg.colmap.precomputed:
        extra = _precomputed(cfg, out)
    elif cfg.colmap.matches:
        extra = _computed(cfg, run, out)
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


def _computed(cfg: Config, run: Path, out: Path) -> dict:
    """COLMAP on its own matches or on this run's, with its camera or calibrate's K."""
    images, query, c = cfg.sfm.images, cfg.localize.query, cfg.colmap
    K = load_K(run / "calibrate" / "K.txt") if c.camera == "fixed" else None
    what = "features, matching, mapping" if c.matches == "colmap" else "mapping on verify's matches"
    with console.status(f"COLMAP on {len(images)} images: {what}"):
        if c.matches == "colmap":
            s = run_colmap(cfg.scene_dir, images, out, query=query, K=K)
        else:
            matches = [io.load_matches(f) for f in sorted((run / "verify").glob("*.npz"))]
            if not matches:
                raise FileNotFoundError(f"no verified matches in {run / 'verify'}")
            s = run_colmap_on_matches(cfg.scene_dir, images, matches, out, query=query, K=K)
    _report(s, images, query)
    return {"source": f"{c.matches} matches", "camera": c.camera,
            "registered": s.registered, "missing": s.missing, "n_points": s.n_points,
            "reprojection_error": s.reprojection_error, "query": query,
            "query_registered": s.query_registered, "query_points": s.query_points}


def _report(s: ColmapSummary, images: list[str], query: str | None) -> None:
    console.print(f"registered [bold]{len(s.registered)}/{len(images)}[/bold] images, "
                  f"{s.n_points} points, {s.reprojection_error:.2f} px")
    if s.missing:
        console.print(f"[yellow]not registered:[/yellow] {', '.join(s.missing)}")
    if query:
        console.print(f"{query}: placed from {s.query_points} points" if s.query_registered
                      else f"[yellow]{query}: not placed[/yellow]")
