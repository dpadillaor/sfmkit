"""The `sfmkit dense` command."""

from __future__ import annotations

from sfmkit.apps.cli._common import console, run_dir
from sfmkit.data import io
from sfmkit.data.colmap import NO_CUDA, dense_available, run_dense
from sfmkit.data.config import load_config


def cmd_dense(args) -> int:
    """COLMAP's dense point cloud of the scene, from the colmap stage's model (CUDA only)."""
    cfg = load_config(args.config)
    if not cfg.dense.enabled:
        console.print("[dim]dense is off in the config (dense.enabled); skipped[/dim]")
        return 0
    if not dense_available():
        console.print(f"[red]{NO_CUDA}[/red]")
        return 1
    run = run_dir(cfg, args.out)
    model, out = run / "colmap", run / "dense"
    if not (model / "images.txt").is_file():
        console.print(f"[red]no COLMAP model in {model}[/red] -- run `sfmkit colmap` first")
        return 1

    size = cfg.dense.max_image_size
    with console.status(f"dense: undistortion, PatchMatch stereo at {size} px, fusion"):
        s = run_dense(model, cfg.scene_dir, cfg.sfm.images, out, max_image_size=size)
    console.print(f"[green]fused[/green] {s.n_points} points from {s.n_images} images "
                  f"-> {out / 'fused.ply'}")
    io.write_manifest(run, "dense", cfg, config_path=args.config, extra={
        "n_images": s.n_images, "n_points": s.n_points, "max_image_size": size,
    })
    return 0
