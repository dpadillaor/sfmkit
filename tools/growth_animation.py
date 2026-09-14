"""The map being built: cameras arriving one by one, points settling.

    python tools/growth_animation.py --format mp4

Runs `reconstruct` again on a finished run's verified matches and keeps the
snapshot it hands out after every step — the poses and the points as they stood
— then draws them from above, interpolating between two steps so the cameras
move rather than jump. The last step is the global refinement, shown twice over
so the pull on the whole model can be seen.

Set in the viewer's colours; `--format webp` for a page that cannot carry
video. Frames are written by `animate.py`, as the other tool here does.
"""

import argparse
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from animate import FORMATS, save  # noqa: E402

from sfmkit.apps.cli._common import load_K  # noqa: E402
from sfmkit.core.metrics import align_to_reference  # noqa: E402
from sfmkit.core.reconstruct import ReconstructionConfig, reconstruct  # noqa: E402
from sfmkit.core.tracks import build_tracks  # noqa: E402
from sfmkit.data import io  # noqa: E402
from sfmkit.data.colmap.model import read_model  # noqa: E402
from sfmkit.data.config import default_run_dir, load_config  # noqa: E402

# The viewer's, so a figure, the viewer and this film agree on who is who.
GROUND, PANEL, LINE = "#161616", "#202020", "#333333"
TEXT, MUTED, FAINT = "#d8d8d8", "#8c8c8c", "#5f5f5f"
OURS, THEIRS, ERROR, SIGNAL = "#f2a93b", "#56a8f5", "#ff6b5a", "#ff4f00"


def ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def centres(poses) -> dict[str, np.ndarray]:
    return {n: p.center for n, p in poses.items()}


def frame(shot_a, shot_b, t: float, limits, shots, at: int, size, dpi=100) -> np.ndarray:
    """The reconstruction between two snapshots, and the log beside it.

    ``t`` runs from 0 at ``shot_a`` to 1 at ``shot_b``: the cameras both know
    move along, the points of one cloud fade out as the other's fade in.
    """
    (x0, x1), (z0, z1) = limits
    fig = plt.figure(figsize=(size[0] / dpi, size[1] / dpi), dpi=dpi, facecolor=GROUND)
    ax = fig.add_axes([0.03, 0.05, 0.50, 0.80])
    ax.set_anchor("C")
    ax.set_facecolor(GROUND)

    for cloud, alpha in ((shot_a.points, 1 - t), (shot_b.points, t)):
        if len(cloud):
            ax.scatter(cloud[:, 0], cloud[:, 2], s=2.4, c=OURS, alpha=0.45 * alpha,
                       linewidths=0, zorder=2)

    a, b = centres(shot_a.poses), centres(shot_b.poses)
    for name, c in b.items():
        here = a[name] * (1 - t) + c * t if name in a else c
        new = name not in a
        ax.scatter(here[0], here[2], s=170 if new else 110, marker="^",
                   color=SIGNAL if new else OURS, edgecolors=GROUND, linewidths=0.8,
                   alpha=ease(t) if new else 1.0, zorder=4)
        if new:  # only the one that just arrived is named; the rest are the cloud
            ax.annotate(name, (here[0], here[2]), fontsize=9, color=TEXT,
                        xytext=(9, 5), textcoords="offset points", alpha=ease(t), zorder=5)

    ax.set_xlim(x0, x1)
    ax.set_ylim(z0, z1)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_color(LINE)
    ax.text(0.5, -0.03, "seen from above  ·  the dense line is the cathedral's facade, "
            "each triangle a photograph", transform=ax.transAxes, fontsize=9.5, color=MUTED,
            ha="center", va="top")

    report = shot_b.report if t > 0.5 else shot_a.report
    fig.text(0.03, 0.925, _headline(report), fontsize=16, color=TEXT, va="bottom")
    fig.text(0.03, 0.885, _readout(report), fontsize=10.5, color=MUTED, va="bottom")

    # The log as it is written: a row per step done, the last one lit. What
    # comes next is not shown because the reconstruction has not chosen it yet.
    now = at if t <= 0.5 else at + 1
    top, step = 0.800, 0.052
    fig.text(0.58, top + 0.038, "step      image     cams     points   err_px",
             fontsize=9.5, color=FAINT, family="monospace")
    fig.text(0.58, 0.075, "err_px: the reprojection error, how far a reconstructed\n"
             "point lands from the spot the photograph saw it",
             fontsize=9, color=FAINT, va="bottom")
    for i, shot in enumerate(shots[:now + 1]):
        r = shot.report
        name = "refine" if r.image == "global refinement" else r.image
        row = (f"{'–' if r.image == 'global refinement' else r.step:>4}   {name:<9}"
               f"{r.n_registered:>5}{r.n_points:>10,}"
               f"{r.rmse_after:>8.2f}" if np.isfinite(r.rmse_after) else
               f"{r.step:>4}   {name:<9}{r.n_registered:>5}{r.n_points:>10,}       –")
        colour = SIGNAL if i == now else MUTED
        fig.text(0.58, top - i * step, row, fontsize=10.5, color=colour, family="monospace",
                 va="top")

    fig.text(0.03, 0.022, "sfmkit · incremental reconstruction of the Plaza de la Virgen",
             fontsize=9, color=FAINT)

    fig.canvas.draw()
    image = np.asarray(fig.canvas.buffer_rgba())[..., :3][..., ::-1].copy()
    plt.close(fig)
    return image


def _headline(report) -> str:
    if report.image == "global refinement":
        return "Global refinement · every camera and point at once"
    if report.step == 0:
        return f"Seed pair · {report.image}"
    return f"Step {report.step} · {report.image} registered"


def _readout(report) -> str:
    bits = [f"{report.n_registered} cameras", f"{report.n_points:,} points"]
    if np.isfinite(report.rmse_after):
        bits.append(f"reprojection error {report.rmse_after:.2f} px")
    if report.n_pnp_correspondences:
        bits.append(f"{report.n_pnp_correspondences} PnP inliers")
    if report.bundle_seconds:
        bits.append(f"bundle {report.bundle_seconds:.1f} s")
    return "     ".join(bits)


def umeyama(src: np.ndarray, dst: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    """The similarity (scale, rotation, translation) that best takes src onto dst."""
    src, dst = np.asarray(src, float), np.asarray(dst, float)
    mu_s, mu_d = src.mean(0), dst.mean(0)
    a, b = src - mu_s, dst - mu_d
    u, sv, vt = np.linalg.svd(a.T @ b / len(src))
    d = np.diag([1.0, 1.0, np.sign(np.linalg.det(u @ vt))])
    R = (u @ d @ vt).T
    variance = max(float(np.mean(np.sum(a**2, 1))), 1e-12)
    scale = float(sv @ np.diag(d)) / variance
    return scale, R, mu_d - scale * R @ mu_s


def against(poses, gt_centres, gt_poses, look=0.25) -> dict[str, np.ndarray]:
    """Our camera centres carried onto COLMAP's frame, by the cameras we share.

    Two cameras leave the rotation about their baseline free, so each camera
    contributes a point ahead of it as well as its centre: with that, even the
    seed pair lands the right way up.
    """
    shared = [n for n in poses if n in gt_centres]
    if len(shared) < 2:
        return {}
    ours = centres(poses)
    # Each set is measured in its own units, so each look-ahead point is placed
    # by its own spread; mixing the two would pull the fit apart.
    def spread(points):
        return max(np.linalg.norm(points[a] - points[b])
                   for a in shared for b in shared) or 1.0

    ours_scale, gt_scale = spread(ours), spread(gt_centres)
    src, dst = [], []
    for n in shared:
        src += [ours[n], ours[n] + look * ours_scale * poses[n].R[2]]
        dst += [gt_centres[n], gt_centres[n] + look * gt_scale * gt_poses[n].R[2]]
    s, R, t = umeyama(np.array(src), np.array(dst))
    return {n: s * R @ c + t for n, c in ours.items()}


def frame_colmap(state_a, state_b, t: float, limits, gt_centres, order, headline, readout,
                 size, dpi=100) -> np.ndarray:
    """The `cameras.png` figure as it stood at a step of the run.

    Same three panels as the figure and the same reading: the two planes with
    their axes, and the gaps as bars. What moves is our cameras.
    """
    (x0, x1), (y0, y1), (z0, z1) = limits
    planes = [(0, 1, "X", "Y", (x0, x1), (y0, y1)), (0, 2, "X", "Z", (x0, x1), (z0, z1))]
    # Fixed boxes, not a layout engine: the error bars grow and shrink from step
    # to step, and nothing that happens to them may move the two planes.
    ratios = [max(0.45, (xs[1] - xs[0]) / max(ys[1] - ys[0], 1e-9)) for *_, xs, ys in planes]
    left, room, gap, bottom, height = 0.05, 0.50, 0.04, 0.16, 0.64
    widths = [(room - gap) * r / sum(ratios) for r in ratios]
    fig = plt.figure(figsize=(size[0] / dpi, size[1] / dpi), dpi=dpi, facecolor=GROUND)
    axes = [fig.add_axes([left, bottom, widths[0], height]),
            fig.add_axes([left + widths[0] + gap, bottom, widths[1], height]),
            fig.add_axes([0.65, bottom, 0.31, height])]
    for ax, (a, b, la, lb, xs, ys) in zip(axes[:2], planes, strict=True):
        ax.set_facecolor(GROUND)
        ax.set_anchor("C")
        for n, c in gt_centres.items():
            seen = n in state_a or n in state_b
            ax.scatter(c[a], c[b], s=100, marker="o",
                       facecolors=THEIRS if seen else "none", edgecolors=THEIRS,
                       linewidths=1.3, alpha=1.0 if seen else 0.4, zorder=3)
        for n, c in state_b.items():
            here = state_a[n] * (1 - t) + c * t if n in state_a else c
            alpha = 1.0 if n in state_a else ease(t)
            ax.plot([here[a], gt_centres[n][a]], [here[b], gt_centres[n][b]], "-",
                    color=ERROR, lw=1.3, alpha=alpha, zorder=4)
            ax.scatter(here[a], here[b], s=140, marker="^", color=OURS, edgecolors=GROUND,
                       linewidths=0.8, alpha=alpha, zorder=5)
            ax.annotate(n, (here[a], here[b]), fontsize=7.5, color=MUTED, alpha=alpha,
                        xytext=(7, 5), textcoords="offset points", zorder=5)
        ax.set_xlim(*xs)
        ax.set_ylim(*ys)
        ax.set_aspect("equal")
        ax.set_xlabel(la, color=MUTED)
        ax.set_ylabel(lb, color=MUTED)
        ax.set_title(f"{la}–{lb}", fontsize=10, color=TEXT)
        ax.grid(color=LINE, lw=0.7, alpha=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(colors=MUTED, labelsize=8.5)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("bottom", "left"):
            ax.spines[side].set_color(LINE)

    # The same gaps as bars, in the order the cameras were registered, so a bar
    # shortening is bundle adjustment pulling that camera into place.
    ax = axes[2]
    ax.set_facecolor(GROUND)
    span = max(np.linalg.norm(c) for c in gt_centres.values()) or 1.0
    widest = 0.0
    for i, n in enumerate(order):
        was = np.linalg.norm(state_a[n] - gt_centres[n]) if n in state_a else None
        now = np.linalg.norm(state_b[n] - gt_centres[n]) if n in state_b else None
        if now is None:
            continue
        value = (now if was is None else was * (1 - t) + now * t) / span
        alpha = 1.0 if was is not None else ease(t)
        widest = max(widest, value)
        ax.barh(i, 100 * value, color=ERROR, alpha=0.65 * alpha, height=0.55)
        ax.annotate(f" {100 * value:.2f}%", (100 * value, i), fontsize=8, color=MUTED,
                    va="center", alpha=alpha)
    ax.set_yticks(np.arange(len(order)), order, fontsize=8.5, color=MUTED)
    ax.set_xlim(0, max(1.4 * 100 * widest, 0.25))
    ax.set_ylim(len(order) - 0.4, -0.6)
    ax.set_xlabel("distance to COLMAP's camera, as % of the scene", fontsize=9, color=MUTED)
    ax.set_title("Position error", fontsize=10, color=TEXT)
    ax.grid(axis="x", color=LINE, lw=0.7, alpha=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", colors=MUTED, labelsize=8.5)
    ax.tick_params(axis="y", length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(LINE)

    handles = [
        plt.Line2D([], [], ls="", marker="^", mfc=OURS, mec=GROUND, label="sfmkit"),
        plt.Line2D([], [], ls="", marker="o", mfc=THEIRS, mec=THEIRS, label="COLMAP"),
        plt.Line2D([], [], ls="", marker="o", mfc="none", mec=THEIRS, label="not registered yet"),
        plt.Line2D([], [], color=ERROR, label="position error"),
    ]
    # Under the two planes it belongs to, not across a figure whose right third
    # is a bar chart that none of these marks appear in.
    middle = left + (room - gap) / 2 + gap / 2
    legend = fig.legend(handles=handles, loc="center", bbox_to_anchor=(middle, 0.085),
                        ncol=4, frameon=False, fontsize=9)
    for text in legend.get_texts():
        text.set_color(MUTED)
    fig.text(0.05, 0.905, headline, fontsize=14.5, color=TEXT, va="bottom")
    fig.text(0.05, 0.865, readout, fontsize=9.5, color=MUTED, va="bottom")

    fig.canvas.draw()
    image = np.asarray(fig.canvas.buffer_rgba())[..., :3][..., ::-1].copy()
    plt.close(fig)
    return image


def bounds(snapshots, margin=0.10):
    """One frame for the whole film, wide enough for the finished model."""
    points = np.vstack([s.points for s in snapshots if len(s.points)])
    cams = np.vstack([c for s in snapshots for c in centres(s.poses).values()])
    x = np.concatenate([np.percentile(points[:, 0], [2, 98]), cams[:, 0]])
    z = np.concatenate([np.percentile(points[:, 2], [2, 98]), cams[:, 2]])
    pad = margin * max(np.ptp(x), np.ptp(z))
    return (x.min() - pad, x.max() + pad), (z.min() - pad, z.max() + pad)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--config", default="projects/valencia/configs/gpu-dense.yaml")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--view", choices=("map", "colmap"), default="map",
                   help="the model being built, or the same cameras against COLMAP's")
    p.add_argument("--format", choices=FORMATS, default="mp4")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--fps", type=int, default=12)
    p.add_argument("--move", type=float, default=0.55, help="seconds a step takes to arrive")
    p.add_argument("--hold", type=float, default=0.85, help="seconds it then stands still")
    p.add_argument("--quality", type=int, default=70)
    p.add_argument("--colours", type=int, default=96)
    p.add_argument("--crf", type=int, default=23)
    args = p.parse_args()

    cfg = load_config(args.config)
    run = default_run_dir(cfg)
    query = cfg.localize.query
    matches = [io.load_matches(f) for f in sorted((run / "verify").glob("*.npz"))]
    matches = [m for m in matches if query not in (m.image0, m.image1)]
    tracks = build_tracks(matches, min_length=cfg.sfm.min_track_length)
    s = cfg.sfm
    options = ReconstructionConfig(
        reference=s.reference, seed=cfg.seed,
        ransac_threshold=s.ransac_threshold, ransac_iterations=s.ransac_iterations,
        pnp_threshold=s.pnp_threshold,
        min_triangulation_angle_deg=s.min_triangulation_angle_deg,
        max_reprojection_error=s.max_reprojection_error,
        min_pnp_correspondences=s.min_pnp_correspondences,
        bundle_solver=s.bundle_solver,
    )

    shots = []
    print(f"reconstructing from {len(matches)} pairs, keeping every step")
    reconstruct(matches, load_K(run / "calibrate" / "K.txt"), tracks, options,
                on_step=lambda snapshot: shots.append(snapshot))
    print(f"{len(shots)} steps")

    moving = max(2, round(args.move * args.fps))
    name = "growth" if args.view == "map" else "against_colmap"
    out = args.out or Path("website/docs/figures") / name

    if args.view == "map":
        limits = bounds(shots)
        size = (args.width, round(args.width * 2 / 3))  # deeper than it is wide
        draw = lambda i, t: frame(shots[i], shots[min(i + 1, len(shots) - 1)], t,  # noqa: E731
                                  limits, shots, i, size)
    else:
        model = read_model(run / "colmap")
        ref = s.reference
        gt_poses = {n: p for n, p in align_to_reference(model["poses"], ref).items()
                    if n != query}
        gt_centres = {n: p.center for n, p in gt_poses.items()}
        states = [against(shot.poses, gt_centres, gt_poses) for shot in shots]
        order, seen = [], set()
        for state in states:  # registration order, so a row is added, never moved
            for n in state:
                if n not in seen:
                    seen.add(n)
                    order.append(n)
        limits = tuple((min(c[i] for c in gt_centres.values()) - 0.25,
                        max(c[i] for c in gt_centres.values()) + 0.25) for i in range(3))
        size = (args.width, round(args.width * 0.46))  # the figure's proportions
        draw = lambda i, t: frame_colmap(  # noqa: E731
            states[i], states[min(i + 1, len(states) - 1)], t, limits, gt_centres, order,
            _headline(shots[min(i + 1, len(shots) - 1)].report if t > 0.5 else shots[i].report),
            _readout(shots[min(i + 1, len(shots) - 1)].report if t > 0.5 else shots[i].report),
            size)

    frames, times = [draw(0, 0.0)], [round(1000 * (args.hold + 1.2))]
    for i in range(len(shots) - 1):
        for k in range(moving):
            frames.append(draw(i, ease((k + 1) / moving)))
            times.append(round(1000 / args.fps))
        times[-1] += round(1000 * args.hold)
    times[-1] += round(1000 * 1.8)  # the finished model is what a viewer reads

    save(frames, times, out, args.format, fps=args.fps, quality=args.quality,
         colours=args.colours, crf=args.crf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
