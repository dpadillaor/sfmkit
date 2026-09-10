"""The `sfmkit reconstruct` command."""

from __future__ import annotations

from rich.console import Group
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table

from sfmkit.apps.cli._common import console, load_K, run_dir
from sfmkit.data import io
from sfmkit.data.config import load_config


def cmd_reconstruct(args) -> int:
    """Build tracks and run incremental SfM with bundle adjustment."""
    from sfmkit.core.reconstruct import ReconstructionConfig, reconstruct
    from sfmkit.core.tracks import build_tracks, track_statistics

    cfg = load_config(args.config)
    run = run_dir(cfg, args.out)
    src = run / "verify"
    files = sorted(src.glob("*.npz"))
    if not files:
        console.print(f"[red]no verified matches in {src}[/red] -- run `sfmkit verify` first")
        return 1

    query = cfg.localize.query
    matches = [io.load_matches(f) for f in files]
    # The query image is localised separately; it must not shape the map.
    matches = [m for m in matches if query not in (m.image0, m.image1)]
    console.print(f"[bold]reconstructing[/bold] from {len(matches)} verified pairs")

    tracks = build_tracks(matches, min_length=cfg.sfm.min_track_length)
    stats = track_statistics(tracks)
    console.print(f"tracks: [bold]{stats['n_tracks']}[/bold]  "
                  f"mean length {stats['mean_length']:.2f}  max {stats['max_length']}  "
                  f"observations {sum(t.length for t in tracks)}")

    s = cfg.sfm
    K = load_K(run / "calibrate" / "K.txt")
    options = ReconstructionConfig(
        reference=s.reference, seed=cfg.seed,
        ransac_threshold=s.ransac_threshold, ransac_iterations=s.ransac_iterations,
        pnp_threshold=s.pnp_threshold,
        min_triangulation_angle_deg=s.min_triangulation_angle_deg,
        max_reprojection_error=s.max_reprojection_error,
        min_pnp_correspondences=s.min_pnp_correspondences,
    )

    # Each step can take tens of seconds, so its row is shown as soon as it is done.
    table = Table(title="incremental reconstruction")
    for c, j in (("step", "right"), ("image", "left"), ("cams", "right"), ("points", "right"),
                 ("pnp", "right"), ("rmse before", "right"), ("rmse after", "right"),
                 ("BA s", "right")):
        table.add_column(c, justify=j)
    if console.is_terminal:
        working = Spinner("dots", text="seed pair: triangulation and bundle adjustment")
        with Live(Group(table, working), console=console, refresh_per_second=8) as live:
            def on_step(r):
                _add_row(table, r)
                working.update(text=f"{r.n_registered} cameras in; next step running "
                                    "(bundle adjustment takes tens of seconds)")

            result = reconstruct(matches, K, tracks, options, on_step=on_step)
            live.update(table)
    else:  # piped, as in the TUI's run tab: a line per step, then the table
        def on_step(r):
            console.print(f"step {r.step}: {r.image}, {r.n_registered} cameras, {r.n_points} "
                          f"points, rmse {r.rmse_after:.3f}, BA {r.bundle_seconds:.1f} s")

        result = reconstruct(matches, K, tracks, options, on_step=on_step)
        for r in result.reports:
            _add_row(table, r)
        console.print(table)

    out = run / "reconstruct"
    out.mkdir(parents=True, exist_ok=True)
    io.save_reconstruction(result.reconstruction, out / "reconstruction.npz")
    if result.before_refinement is not None:
        io.save_reconstruction(result.before_refinement,
                               out / "reconstruction_before_refinement.npz")
    io.write_manifest(run, "reconstruct", cfg, config_path=args.config, extra={
        "tracks": stats,
        "n_observations": sum(t.length for t in tracks),
        "steps": [vars(r) for r in result.reports],
        "n_cameras": len(result.reconstruction.poses),
        "n_points": result.reconstruction.n_points,
    })
    console.print(f"[green]registered[/green] {len(result.reconstruction.poses)} cameras, "
                  f"{result.reconstruction.n_points} points")
    return 0


def _add_row(table: Table, r) -> None:
    table.add_row(str(r.step), r.image, str(r.n_registered), str(r.n_points),
                  str(r.n_pnp_correspondences), f"{r.rmse_before:.3f}",
                  f"{r.rmse_after:.3f}", f"{r.bundle_seconds:.1f}")
