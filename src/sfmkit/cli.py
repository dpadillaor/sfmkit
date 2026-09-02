"""Command line interface.

One entry point, one subcommand per pipeline stage. Stage order lives in the
Makefile and in the config, not in module names, so inserting a stage does not
rename anything.

Each stage reads an explicit input directory and writes an explicit output
directory, and every output carries a manifest. That contract is the fix for the
original pipeline's real defect: there, stages found their inputs through
hardcoded relative paths, results were never saved at all, and a missing file
was patched by pasting numbers into the next script's source.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from sfmkit import io
from sfmkit.config import Config, load_config
from sfmkit.metrics import compare_poses

console = Console()


def _progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    )


def _load_K(path) -> np.ndarray:
    return np.loadtxt(path).reshape(3, 3)


def _pairs_of(cfg: Config) -> list[tuple[str, str]]:
    """Which image pairs to match: all of them, or only those touching the reference."""
    names = cfg.image_names
    if cfg.exhaustive:
        return list(itertools.combinations(names, 2))
    ref = cfg.reference or names[0]
    return [(ref, n) for n in names if n != ref]


# --------------------------------------------------------------------------- match
def cmd_match(args) -> int:
    """Detect and match features for every configured pair (needs a GPU to be quick)."""
    from sfmkit.features import match_pairs

    cfg = load_config(args.config)
    out = Path(args.out) / "matches"
    pairs = _pairs_of(cfg)
    if cfg.query:
        pairs += [(cfg.reference or cfg.image_names[0], cfg.query)]

    console.print(f"[bold]matching[/bold] {len(pairs)} pairs from {cfg.images_dir}")
    with _progress() as p:
        task = p.add_task("extract + match", total=len(pairs))
        written = match_pairs(
            Path(cfg.images_dir), pairs, out,
            max_keypoints=cfg.max_keypoints,
            on_pair=lambda a, b, n: p.advance(task),
        )
    io.write_manifest(args.out, "match", cfg, extra={"n_pairs": len(written)})
    console.print(f"[green]wrote[/green] {len(written)} match files to {out}")
    return 0


# -------------------------------------------------------------------------- verify
def cmd_verify(args) -> int:
    """Geometric verification: fit a fundamental matrix and keep the inliers."""
    from sfmkit.robust import ransac_fundamental

    cfg = load_config(args.config)
    src = Path(args.out) / "matches"
    dst = Path(args.out) / "verified"
    files = sorted(src.glob("*.npz"))
    if not files:
        console.print(f"[red]no matches in {src}[/red] -- run `sfmkit match` first")
        return 1

    rows, kept = [], 0
    with _progress() as p:
        task = p.add_task("RANSAC", total=len(files))
        for f in files:
            m = io.load_matches(f)
            x0, x1 = m.keypoints0[m.pairs[:, 0]], m.keypoints1[m.pairs[:, 1]]
            res = ransac_fundamental(
                x0, x1, threshold=cfg.ransac_threshold,
                max_iterations=cfg.ransac_iterations, seed=cfg.seed,
            )
            ok = res.converged and res.n_inliers >= cfg.min_inliers
            if ok:
                m.inliers = res.inliers
                io.save_matches(m, dst / f.name)
                kept += 1
            rows.append({
                "pair": f"{m.image0}-{m.image1}", "matches": m.n_matches,
                "inliers": int(res.n_inliers),
                "ratio": round(res.n_inliers / max(m.n_matches, 1), 3),
                "iterations": res.n_iterations, "kept": ok,
            })
            p.advance(task)

    table = Table(title="geometric verification", show_footer=False)
    for c in ("pair", "matches", "inliers", "ratio", "iters", "kept"):
        table.add_column(c, justify="right" if c != "pair" else "left")
    for r in sorted(rows, key=lambda r: -r["inliers"]):
        style = "" if r["kept"] else "dim red"
        table.add_row(r["pair"], str(r["matches"]), str(r["inliers"]), f"{r['ratio']:.2f}",
                      str(r["iterations"]), "yes" if r["kept"] else "no", style=style)
    console.print(table)

    io.write_manifest(args.out, "verify", cfg, extra={"pairs": rows, "n_kept": kept})
    console.print(f"[green]kept[/green] {kept}/{len(files)} pairs -> {dst}")
    return 0


# ---------------------------------------------------------------------- reconstruct
def cmd_reconstruct(args) -> int:
    """Build tracks and run incremental SfM with bundle adjustment."""
    from sfmkit.reconstruct import ReconstructionConfig, reconstruct
    from sfmkit.tracks import build_tracks, track_statistics

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

    K = _load_K(cfg.intrinsics)
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
    io.write_manifest(args.out, "reconstruct", cfg, extra={
        "tracks": stats,
        "n_observations": sum(t.length for t in tracks),
        "steps": [vars(r) for r in result.reports],
        "n_cameras": len(result.reconstruction.poses),
        "n_points": result.reconstruction.n_points,
    })
    console.print(f"[green]registered[/green] {len(result.reconstruction.poses)} cameras, "
                  f"{result.reconstruction.n_points} points")
    return 0


# -------------------------------------------------------------------------- localize
def cmd_localize(args) -> int:
    """Localise the query image against the reconstruction (the historical photo)."""
    from sfmkit.localize import localize_image

    cfg = load_config(args.config)
    if not cfg.query:
        console.print("[red]no `query` set in the config[/red]")
        return 1

    rec = io.load_reconstruction(Path(args.out) / "reconstruction.npz")
    verified = Path(args.out) / "verified"
    q_files = [f for f in verified.glob("*.npz") if cfg.query in f.stem]
    if not q_files:
        console.print(f"[red]no verified pairs involving {cfg.query}[/red]")
        return 1

    seeds = list(range(args.trials))
    results = []
    with _progress() as p:
        task = p.add_task(f"localising {cfg.query}", total=len(seeds))
        for s in seeds:
            r = localize_image(rec, [io.load_matches(f) for f in q_files], cfg.query, seed=s)
            if r is not None:
                results.append(r)
            p.advance(task)

    if not results:
        console.print("[red]localisation failed[/red]")
        return 1

    # Report a distribution, not a single number: the original's unseeded RANSAC
    # gave rotation errors from 5 to 31 degrees on the same input.
    centres = np.array([r.pose.center for r in results])
    table = Table(title=f"localisation of {cfg.query} over {len(results)} seeds")
    for c in ("quantity", "median", "min", "max", "spread"):
        table.add_column(c, justify="right" if c != "quantity" else "left")
    for label, v in (("inliers", np.array([r.n_inliers for r in results], dtype=float)),
                     ("reproj. RMSE", np.array([r.rmse for r in results])),
                     ("centre x", centres[:, 0]), ("centre y", centres[:, 1]),
                     ("centre z", centres[:, 2])):
        table.add_row(label, f"{np.median(v):.3f}", f"{v.min():.3f}",
                      f"{v.max():.3f}", f"{v.max() - v.min():.3f}")
    console.print(table)

    best = min(results, key=lambda r: r.rmse)
    np.savez(Path(args.out) / "query_pose.npz",
             R=best.pose.R, t=best.pose.t,
             centres=centres, rmse=np.array([r.rmse for r in results]),
             inliers=np.array([r.n_inliers for r in results]))
    io.write_manifest(args.out, "localize", cfg, extra={
        "query": cfg.query, "trials": len(results),
        "rmse_median": float(np.median([r.rmse for r in results])),
        "centre_spread": float(np.linalg.norm(centres.max(0) - centres.min(0))),
    })
    console.print(f"[green]localised[/green] {cfg.query}, best RMSE {best.rmse:.3f}px")
    return 0


# -------------------------------------------------------------------------- evaluate
def cmd_evaluate(args) -> int:
    """Compare the reconstruction against a COLMAP model."""
    from sfmkit.colmap import read_model

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
    io.write_manifest(args.out, "evaluate", cfg, extra={
        "mean_rotation_error_deg": cmp["mean_rotation_error_deg"],
        "max_rotation_error_deg": cmp["max_rotation_error_deg"],
        "scale": cmp["scale"], "n_cameras": cmp["n_cameras"],
    })
    return 0


# ------------------------------------------------------------------------ figures
def cmd_figures(args) -> int:
    """Render the comparison figures for a finished run."""
    from sfmkit.colmap import read_model
    from sfmkit.viz import plot_camera_layout, plot_comparison

    cfg = load_config(args.config)
    rec = io.load_reconstruction(Path(args.out) / "reconstruction.npz")
    model = read_model(cfg.colmap_model)
    ref = cfg.reference or rec.registered[0]
    out = Path(args.out) / "figures"
    paths = [
        plot_comparison(rec, model, ref, out / "comparison.png"),
        plot_camera_layout(rec, model, ref, out / "cameras.png"),
    ]
    for p in paths:
        console.print(f"[green]wrote[/green] {p}")
    return 0


# ------------------------------------------------------------------------ changes
def cmd_changes(args) -> int:
    """Align the historical photograph to a modern one and flag what differs."""
    import cv2

    from sfmkit.changes import detect_changes

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
    io.write_manifest(args.out, "changes", cfg, extra={
        "query": cfg.query, "against": target,
        "homography_inliers": result.n_inliers,
        "changed_fraction": result.changed_fraction,
        "threshold": args.threshold,
    })
    console.print(f"[green]wrote[/green] {out}")
    return 0


# ---------------------------------------------------------------------------- ui
def cmd_ui(args) -> int:
    """Browse and compare runs in a terminal interface."""
    try:
        from sfmkit.tui import run as run_tui
    except ImportError:
        console.print("[red]the TUI needs textual:[/red] pip install 'sfmkit[tui]'")
        return 1
    run_tui(args.runs)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sfmkit", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="command", required=True)

    def stage(name, fn, help_):
        s = sub.add_parser(name, help=help_)
        s.add_argument("--config", required=True, help="YAML experiment config")
        s.add_argument("--out", required=True, help="run directory for inputs and outputs")
        s.set_defaults(func=fn)
        return s

    stage("match", cmd_match, "detect and match features for every configured pair")
    stage("verify", cmd_verify, "fit fundamental matrices and keep geometric inliers")
    stage("reconstruct", cmd_reconstruct, "build tracks and run incremental SfM + BA")
    loc = stage("localize", cmd_localize, "localise the query image against the reconstruction")
    loc.add_argument("--trials", type=int, default=20,
                     help="seeds to run, so the pose is reported as a distribution")
    stage("evaluate", cmd_evaluate, "compare the reconstruction against a COLMAP model")
    stage("figures", cmd_figures, "render comparison figures for a finished run")
    ch = stage("changes", cmd_changes, "detect scene change between the query and a modern image")
    ch.add_argument("--against", help="modern image to compare against (default: the reference)")
    ch.add_argument("--threshold", type=float, default=0.38,
                    help="dissimilarity threshold in [0, 1]")

    ui = sub.add_parser("ui", help="browse and compare runs in a terminal interface")
    ui.add_argument("--runs", default="runs", help="directory holding run outputs")
    ui.set_defaults(func=cmd_ui)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as e:
        console.print(f"[red]missing file:[/red] {e}")
        return 1
    except Exception as e:  # surface the failure, do not print a bare traceback
        console.print(f"[red]{type(e).__name__}:[/red] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
