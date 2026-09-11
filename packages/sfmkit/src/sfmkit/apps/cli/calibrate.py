"""The `sfmkit calibrate` command."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np

from sfmkit.apps.cli._common import console, load_K, run_dir
from sfmkit.data import io
from sfmkit.data.config import load_config
from sfmkit.data.io import image_file


def cmd_calibrate(args) -> int:
    """Intrinsics for the run: from chessboard photos, a precomputed K, or EXIF."""
    cfg = load_config(args.config)
    run = run_dir(cfg, args.out)
    out = run / "calibrate"
    out.mkdir(parents=True, exist_ok=True)
    c = cfg.calibrate

    if c.images:
        from sfmkit.core.calibration import calibrate_chessboard

        pattern = Path(c.images)
        files = sorted(pattern.parent.glob(pattern.name))
        if not files:
            console.print(f"[red]no calibration images match {c.images}[/red]")
            return 1
        images = [io.read_image(f, grey=True) for f in files]
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
    elif c.exif:
        extra = _from_exif(cfg, out)
        if extra is None:
            return 1
    else:
        console.print("[red]set `calibrate.images`, `calibrate.intrinsics` or "
                      "`calibrate.exif`[/red]")
        return 1

    K = load_K(out / "K.txt")
    io.write_manifest(run, "calibrate", cfg, config_path=args.config,
                      extra={**extra, "K": K.tolist()})
    console.print(f"[green]f[/green] {K[0, 0]:.1f}, {K[1, 1]:.1f}  "
                  f"[green]c[/green] {K[0, 2]:.1f}, {K[1, 2]:.1f}")
    return 0


def _from_exif(cfg, out: Path) -> dict | None:
    """K from the scene photos' EXIF, which must agree on one camera setting."""
    from sfmkit.core.calibration import intrinsics_from_focal_35mm
    from sfmkit.data.exif import read_camera

    shots = {n: read_camera(image_file(cfg.scene_dir, n)) for n in cfg.sfm.images}
    # Digital zoom is a crop: a photo zoomed 1.17x is a camera 17% longer.
    settings = {(round(s.effective_35mm, 2), s.size) for s in shots.values()}
    if len(settings) != 1:
        found = ", ".join(f"{n}: {s.focal_35mm:g} mm x{s.zoom:g} zoom, {s.size[0]}x{s.size[1]}"
                          for n, s in shots.items())
        console.print(f"[red]the photos do not share one camera setting[/red] ({found})")
        return None
    shot = next(iter(shots.values()))
    w, h = cfg.calibrate.sensor_aspect
    K = intrinsics_from_focal_35mm(shot.effective_35mm, *shot.size, sensor_aspect=w / h)
    np.savetxt(out / "K.txt", K)
    console.print(f"K from EXIF: {shot.model or 'unknown camera'}, "
                  f"{shot.effective_35mm:g} mm equivalent, {shot.size[0]}x{shot.size[1]}")
    return {"source": "exif", "camera": shot.model, "focal_mm": shot.focal_mm,
            "focal_35mm": shot.focal_35mm, "zoom": shot.zoom, "sensor_aspect": [w, h]}
