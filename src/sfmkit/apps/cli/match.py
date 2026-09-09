"""The `sfmkit match` command."""

from __future__ import annotations

from pathlib import Path

from sfmkit.apps.cli._common import console, pairs_of, progress
from sfmkit.data import io
from sfmkit.data.config import load_config


def cmd_match(args) -> int:
    """Detect and match features for every configured pair (needs a GPU to be quick)."""
    from sfmkit.data.features import match_pairs

    cfg = load_config(args.config)
    out = Path(args.out) / "matches"
    pairs = pairs_of(cfg)
    if cfg.query:
        pairs += [(cfg.reference or cfg.image_names[0], cfg.query)]

    console.print(f"[bold]matching[/bold] {len(pairs)} pairs from {cfg.images_dir}")
    with progress() as p:
        task = p.add_task("extract + match", total=len(pairs))
        written = match_pairs(
            Path(cfg.images_dir), pairs, out,
            max_keypoints=cfg.max_keypoints,
            on_pair=lambda a, b, n: p.advance(task),
        )
    io.write_manifest(args.out, "match", cfg, extra={"n_pairs": len(written)},
                      config_path=args.config)
    console.print(f"[green]wrote[/green] {len(written)} match files to {out}")
    return 0
