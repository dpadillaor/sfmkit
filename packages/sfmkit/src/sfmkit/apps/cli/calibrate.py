"""The `sfmkit calibrate` command."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np

from sfmkit.apps.cli._common import console, load_K, run_dir
from sfmkit.data import io
from sfmkit.data.config import load_config


def cmd_calibrate(args) -> int:
    """Intrinsics for the run: from chessboard photos, or a precomputed K."""
    cfg = load_config(args.config)
    run = run_dir(cfg, args.out)
    out = run / "calibrate"
    out.mkdir(parents=True, exist_ok=True)
    c = cfg.calibrate

    if c.images:
        import cv2

        from sfmkit.core.calibration import calibrate_chessboard

        pattern = Path(c.images)
        files = sorted(pattern.parent.glob(pattern.name))
        if not files:
            console.print(f"[red]no calibration images match {c.images}[/red]")
            return 1
        images = [cv2.imread(str(f), cv2.IMREAD_GRAYSCALE) for f in files]
        cal = calibrate_chessboard(images, tuple(c.pattern))
        np.savetxt(out / "K.txt", cal.K)
        np.savetxt(out / "dist.txt", cal.dist)
        extra = {"source": "chessboard", "rmse": cal.rmse,
                 "images": [files[i].name for i in cal.used], "n_images": len(files)}
        console.print(f"board found in {len(cal.used)}/{len(files)} images, "
                      f"RMSE [bold]{cal.rmse:.3f}px[/bold]")
    elif c.intrinsics:
        shutil.copyfile(c.intrinsics, out / "K.txt")
        extra = {"source": "precomputed"}
        console.print(f"using precomputed intrinsics from {c.intrinsics}")
    else:
        console.print("[red]set `calibrate.images` or `calibrate.intrinsics`[/red]")
        return 1

    K = load_K(out / "K.txt")
    io.write_manifest(run, "calibrate", cfg, config_path=args.config,
                      extra={**extra, "K": K.tolist()})
    console.print(f"[green]f[/green] {K[0, 0]:.1f}, {K[1, 1]:.1f}  "
                  f"[green]c[/green] {K[0, 2]:.1f}, {K[1, 2]:.1f}")
    return 0
