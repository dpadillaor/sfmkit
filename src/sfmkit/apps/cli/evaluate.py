"""The `sfmkit evaluate` command."""

from __future__ import annotations

import json
from pathlib import Path

from rich.table import Table

from sfmkit.apps.cli._common import console
from sfmkit.core.metrics import compare_poses
from sfmkit.data import io
from sfmkit.data.config import load_config


def cmd_evaluate(args) -> int:
    """Compare the reconstruction against a COLMAP model."""
    from sfmkit.data.colmap import read_model

    cfg = load_config(args.config)
    rec = io.load_reconstruction(Path(args.out) / "reconstruction.npz")
    if not cfg.colmap_model:
        console.print("[red]no `colmap_model` in the config[/red]")
        return 1
    model = read_model(cfg.colmap_model)

    ref = cfg.reference or rec.registered[0]
    cmp = compare_poses(rec.poses, model["poses"], reference=ref)

    table = Table(title=f"vs COLMAP  (scale {cmp['scale']:.4f}, reference {ref})")
    for c, j in (("camera", "left"), ("rotation err (deg)", "right"),
                 ("position err", "right"), ("dist. from ref", "right")):
        table.add_column(c, justify=j)
    for r in cmp["cameras"]:
        table.add_row(r["camera"], f"{r['rotation_error_deg']:.3f}",
                      f"{r['position_error']:.4f}", f"{r['distance_from_reference']:.3f}")
    console.print(table)
    console.print(f"mean rotation error [bold]{cmp['mean_rotation_error_deg']:.3f}°[/bold], "
                  f"max {cmp['max_rotation_error_deg']:.3f}°, "
                  f"{cmp['n_cameras']} shared cameras")

    (Path(args.out) / "evaluation.json").write_text(json.dumps(cmp, indent=2, default=float))
    io.write_manifest(args.out, "evaluate", cfg, config_path=args.config, extra={
        "mean_rotation_error_deg": cmp["mean_rotation_error_deg"],
        "max_rotation_error_deg": cmp["max_rotation_error_deg"],
        "scale": cmp["scale"], "n_cameras": cmp["n_cameras"],
    })
    return 0
