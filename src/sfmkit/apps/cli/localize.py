"""The `sfmkit localize` command."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from rich.table import Table

from sfmkit.apps.cli._common import console, progress
from sfmkit.data import io
from sfmkit.data.config import load_config


def cmd_localize(args) -> int:
    """Localise the query image against the reconstruction (the historical photo)."""
    from sfmkit.core.localize import localize_image

    cfg = load_config(args.config)
    if not cfg.query:
        console.print("[red]no `query` set in the config[/red]")
        return 1

    rec = io.load_reconstruction(Path(args.out) / "reconstruction.npz")
    verified = Path(args.out) / "verified"
    q_files = [f for f in verified.glob("*.npz") if cfg.query in f.stem]
    if not q_files:
        console.print(f"[red]no verified pairs involving {cfg.query}[/red]")
        return 1

    seeds = list(range(args.trials))
    results = []
    with progress() as p:
        task = p.add_task(f"localising {cfg.query}", total=len(seeds))
        for s in seeds:
            r = localize_image(rec, [io.load_matches(f) for f in q_files], cfg.query, seed=s)
            if r is not None:
                results.append(r)
            p.advance(task)

    if not results:
        console.print("[red]localisation failed[/red]")
        return 1

    # Report a distribution, not a single number: the original's unseeded RANSAC
    # gave rotation errors from 5 to 31 degrees on the same input.
    centres = np.array([r.pose.center for r in results])
    table = Table(title=f"localisation of {cfg.query} over {len(results)} seeds")
    for c in ("quantity", "median", "min", "max", "spread"):
        table.add_column(c, justify="right" if c != "quantity" else "left")
    for label, v in (("inliers", np.array([r.n_inliers for r in results], dtype=float)),
                     ("reproj. RMSE", np.array([r.rmse for r in results])),
                     ("centre x", centres[:, 0]), ("centre y", centres[:, 1]),
                     ("centre z", centres[:, 2])):
        table.add_row(label, f"{np.median(v):.3f}", f"{v.min():.3f}",
                      f"{v.max():.3f}", f"{v.max() - v.min():.3f}")
    console.print(table)

    best = min(results, key=lambda r: r.rmse)
    np.savez(Path(args.out) / "query_pose.npz",
             R=best.pose.R, t=best.pose.t,
             centres=centres, rmse=np.array([r.rmse for r in results]),
             inliers=np.array([r.n_inliers for r in results]))
    io.write_manifest(args.out, "localize", cfg, config_path=args.config, extra={
        "query": cfg.query, "trials": len(results),
        "rmse_median": float(np.median([r.rmse for r in results])),
        "centre_spread": float(np.linalg.norm(centres.max(0) - centres.min(0))),
    })
    console.print(f"[green]localised[/green] {cfg.query}, best RMSE {best.rmse:.3f}px")
    return 0
