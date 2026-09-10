"""The `sfmkit localize` command."""

from __future__ import annotations

import numpy as np
from rich.table import Table

from sfmkit.apps.cli._common import console, progress, run_dir
from sfmkit.data import io
from sfmkit.data.config import load_config


def cmd_localize(args) -> int:
    """Localise the query image against the reconstruction (the historical photo)."""
    from sfmkit.core.localize import localize_image

    cfg = load_config(args.config)
    query = cfg.localize.query
    if not query:
        console.print("[red]no `localize.query` set in the config[/red]")
        return 1

    run = run_dir(cfg, args.out)
    rec = io.load_reconstruction(run / "reconstruct" / "reconstruction.npz")
    q_files = [f for f in (run / "verify").glob("*.npz") if query in f.stem]
    if not q_files:
        console.print(f"[red]no verified pairs involving {query}[/red]")
        return 1

    seeds = list(range(args.trials))
    results = []
    with progress() as p:
        task = p.add_task(f"localising {query}", total=len(seeds))
        for s in seeds:
            r = localize_image(rec, [io.load_matches(f) for f in q_files], query, seed=s)
            if r is not None:
                results.append(r)
            p.advance(task)

    if not results:
        console.print("[red]localisation failed[/red]")
        return 1

    # Reported as a distribution rather than a single value: estimating eleven
    # parameters from six correspondences varies noticeably between seeds.
    centres = np.array([r.pose.center for r in results])
    table = Table(title=f"localisation of {query} over {len(results)} seeds")
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
    out = run / "localize"
    out.mkdir(parents=True, exist_ok=True)
    np.savez(out / "query_pose.npz",
             R=best.pose.R, t=best.pose.t, K=best.K,
             centres=centres, rmse=np.array([r.rmse for r in results]),
             inliers=np.array([r.n_inliers for r in results]))
    io.write_manifest(run, "localize", cfg, config_path=args.config, extra={
        "query": query, "trials": len(results),
        "rmse_median": float(np.median([r.rmse for r in results])),
        "centre_spread": float(np.linalg.norm(centres.max(0) - centres.min(0))),
    })
    console.print(f"[green]localised[/green] {query}, best RMSE {best.rmse:.3f}px")
    return 0
