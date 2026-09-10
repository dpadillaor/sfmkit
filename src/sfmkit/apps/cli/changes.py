"""The `sfmkit changes` command."""

from __future__ import annotations

import numpy as np

from sfmkit.apps.cli._common import console, run_dir
from sfmkit.data import io
from sfmkit.data.config import load_config


def cmd_changes(args) -> int:
    """Align the historical photograph to a modern one and flag what differs."""
    import cv2

    from sfmkit.core.changes import detect_changes

    cfg = load_config(args.config)
    query = cfg.localize.query
    if not query:
        console.print("[red]no `localize.query` set in the config[/red]")
        return 1

    run = run_dir(cfg, args.out)
    target = args.against or cfg.sfm.reference or cfg.sfm.images[0]
    hit = [f for f in (run / "verify").glob("*.npz")
           if {query, target} == set(f.stem.split("__"))]
    if not hit:
        console.print(f"[red]no verified pair {query}/{target}[/red]")
        return 1

    m = io.load_matches(hit[0])
    p0, p1 = m.points()
    src, dst = (p0, p1) if m.image0 == query else (p1, p0)

    images = cfg.scene_dir
    read = lambda n: cv2.imread(str(next(p for p in [images / n, *images.glob(f"{n}.*")]  # noqa: E731
                                         if p.is_file())), cv2.IMREAD_COLOR)
    hist, mod = read(query), read(target)
    if hist is None or mod is None:
        console.print("[red]could not read the images[/red]")
        return 1

    result = detect_changes(hist, mod, src, dst, threshold=args.threshold, seed=cfg.seed)
    console.print(f"homography from [bold]{result.n_inliers}[/bold] inliers; "
                  f"[bold]{100 * result.changed_fraction:.1f}%[/bold] of the overlap flagged")

    out = run / "changes"
    out.mkdir(parents=True, exist_ok=True)
    overlay = mod.copy()
    overlay[result.mask] = (0.45 * overlay[result.mask] +
                            0.55 * np.array([0, 0, 255])).astype(np.uint8)
    cv2.imwrite(str(out / f"{query}_warped.png"), result.warped)
    cv2.imwrite(str(out / f"difference_{query}_vs_{target}.png"), result.difference)
    cv2.imwrite(str(out / f"overlay_{query}_on_{target}.png"), result.overlay)
    cv2.imwrite(str(out / f"matched_difference_{query}_vs_{target}.png"),
                _legend(result.matched_difference, "bright: differs    dark: the same "
                                                   "(the old photo's tones matched to today's)"))
    cv2.imwrite(str(out / f"changes_{query}_vs_{target}.png"), overlay)
    cv2.imwrite(str(out / "score.png"), (255 * result.score).astype(np.uint8))
    io.write_manifest(run, "changes", cfg, config_path=args.config, extra={
        "query": query, "against": target,
        "homography_inliers": result.n_inliers,
        "changed_fraction": result.changed_fraction,
        "threshold": args.threshold,
    })
    console.print(f"[green]wrote[/green] {out}")
    return 0


def _legend(image: np.ndarray, text: str) -> np.ndarray:
    """``image`` under a black strip saying how to read it."""
    import cv2

    h = max(40, image.shape[1] // 40)
    strip = np.zeros((h, image.shape[1], 3), np.uint8)
    scale = h / 45
    cv2.putText(strip, text, (h // 3, int(h * 0.7)), cv2.FONT_HERSHEY_SIMPLEX, scale,
                (255, 255, 255), max(1, int(2 * scale)), cv2.LINE_AA)
    return np.vstack([strip, image])
