"""The `sfmkit changes` command."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from sfmkit.apps.cli._common import console
from sfmkit.data import io
from sfmkit.data.config import load_config


def cmd_changes(args) -> int:
    """Align the historical photograph to a modern one and flag what differs."""
    import cv2

    from sfmkit.core.changes import detect_changes

    cfg = load_config(args.config)
    if not cfg.query:
        console.print("[red]no `query` set in the config[/red]")
        return 1

    target = args.against or cfg.reference or cfg.image_names[0]
    verified = Path(args.out) / "verified"
    hit = [f for f in verified.glob("*.npz")
           if {cfg.query, target} == set(f.stem.split("__"))]
    if not hit:
        console.print(f"[red]no verified pair {cfg.query}/{target}[/red]")
        return 1

    m = io.load_matches(hit[0])
    p0, p1 = m.points()
    src, dst = (p0, p1) if m.image0 == cfg.query else (p1, p0)

    images = Path(cfg.images_dir)
    read = lambda n: cv2.imread(str(next(p for p in [images / n, *images.glob(f"{n}.*")]  # noqa: E731
                                         if p.is_file())), cv2.IMREAD_COLOR)
    hist, mod = read(cfg.query), read(target)
    if hist is None or mod is None:
        console.print("[red]could not read the images[/red]")
        return 1

    result = detect_changes(hist, mod, src, dst, threshold=args.threshold, seed=cfg.seed)
    console.print(f"homography from [bold]{result.n_inliers}[/bold] inliers; "
                  f"[bold]{100 * result.changed_fraction:.1f}%[/bold] of the overlap flagged")

    out = Path(args.out) / "changes"
    out.mkdir(parents=True, exist_ok=True)
    overlay = mod.copy()
    overlay[result.mask] = (0.45 * overlay[result.mask] +
                            0.55 * np.array([0, 0, 255])).astype(np.uint8)
    cv2.imwrite(str(out / f"{cfg.query}_warped.png"), result.warped)
    cv2.imwrite(str(out / f"changes_{cfg.query}_vs_{target}.png"), overlay)
    cv2.imwrite(str(out / "score.png"), (255 * result.score).astype(np.uint8))
    io.write_manifest(args.out, "changes", cfg, config_path=args.config, extra={
        "query": cfg.query, "against": target,
        "homography_inliers": result.n_inliers,
        "changed_fraction": result.changed_fraction,
        "threshold": args.threshold,
    })
    console.print(f"[green]wrote[/green] {out}")
    return 0
