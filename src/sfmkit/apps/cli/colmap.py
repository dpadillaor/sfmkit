"""The `sfmkit colmap` command."""

from __future__ import annotations

import shutil

from sfmkit.apps.cli._common import console, run_dir
from sfmkit.data import io
from sfmkit.data.config import load_config

FILES = ("cameras.txt", "images.txt", "points3D.txt")


def cmd_colmap(args) -> int:
    """The COLMAP model this run is scored against."""
    from sfmkit.data.colmap import read_model

    cfg = load_config(args.config)
    run = run_dir(cfg, args.out)
    out = run / "colmap"

    if cfg.colmap.matches:
        console.print(f"[red]colmap.matches: {cfg.colmap.matches} is not implemented yet;[/red] "
                      "use `colmap.precomputed`")
        return 1
    if not cfg.colmap.precomputed:
        console.print("[red]set `colmap.precomputed` or `colmap.matches`[/red]")
        return 1

    out.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copyfile(f"{cfg.colmap.precomputed}/{name}", out / name)
    model = read_model(out)
    io.write_manifest(run, "colmap", cfg, config_path=args.config, extra={
        "source": "precomputed", "n_images": len(model["poses"]),
    })
    console.print(f"using precomputed model from {cfg.colmap.precomputed}: "
                  f"{len(model['poses'])} images")
    return 0
