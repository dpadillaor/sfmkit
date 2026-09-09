"""The `sfmkit reconstruct` command."""

from __future__ import annotations

from pathlib import Path

from rich.table import Table

from sfmkit.apps.cli._common import console, load_K
from sfmkit.data import io
from sfmkit.data.config import load_config


def cmd_reconstruct(args) -> int:
    """Build tracks and run incremental SfM with bundle adjustment."""
    from sfmkit.core.reconstruct import ReconstructionConfig, reconstruct
    from sfmkit.core.tracks import build_tracks, track_statistics

    cfg = load_config(args.config)
    src = Path(args.out) / "verified"
    files = sorted(src.glob("*.npz"))
    if not files:
        console.print(f"[red]no verified matches in {src}[/red] -- run `sfmkit verify` first")
        return 1

    query = cfg.query
    matches = [io.load_matches(f) for f in files]
    # The query image is localised separately; it must not shape the map.
    matches = [m for m in matches if query not in (m.image0, m.image1)]
    console.print(f"[bold]reconstructing[/bold] from {len(matches)} verified pairs")

    tracks = build_tracks(matches, min_length=cfg.min_track_length)
    stats = track_statistics(tracks)
    console.print(f"tracks: [bold]{stats['n_tracks']}[/bold]  "
                  f"mean length {stats['mean_length']:.2f}  max {stats['max_length']}  "
                  f"observations {sum(t.length for t in tracks)}")

    K = load_K(cfg.intrinsics)
    result = reconstruct(matches, K, tracks, ReconstructionConfig(
        reference=cfg.reference, seed=cfg.seed,
        ransac_threshold=cfg.ransac_threshold, ransac_iterations=cfg.ransac_iterations,
        pnp_threshold=cfg.pnp_threshold,
        min_triangulation_angle_deg=cfg.min_triangulation_angle_deg,
        max_reprojection_error=cfg.max_reprojection_error,
        min_pnp_correspondences=cfg.min_pnp_correspondences,
    ))

    table = Table(title="incremental reconstruction")
    for c, j in (("step", "right"), ("image", "left"), ("cams", "right"), ("points", "right"),
                 ("pnp", "right"), ("rmse before", "right"), ("rmse after", "right"),
                 ("BA s", "right")):
        table.add_column(c, justify=j)
    for r in result.reports:
        table.add_row(str(r.step), r.image, str(r.n_registered), str(r.n_points),
                      str(r.n_pnp_correspondences), f"{r.rmse_before:.3f}",
                      f"{r.rmse_after:.3f}", f"{r.bundle_seconds:.1f}")
    console.print(table)

    io.save_reconstruction(result.reconstruction, Path(args.out) / "reconstruction.npz")
    if result.before_refinement is not None:
        io.save_reconstruction(result.before_refinement,
                               Path(args.out) / "reconstruction_before_refinement.npz")
    io.write_manifest(args.out, "reconstruct", cfg, config_path=args.config, extra={
        "tracks": stats,
        "n_observations": sum(t.length for t in tracks),
        "steps": [vars(r) for r in result.reports],
        "n_cameras": len(result.reconstruction.poses),
        "n_points": result.reconstruction.n_points,
    })
    console.print(f"[green]registered[/green] {len(result.reconstruction.poses)} cameras, "
                  f"{result.reconstruction.n_points} points")
    return 0
