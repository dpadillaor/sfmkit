"""Figures: reconstruction comparisons, camera layouts, matches and residuals."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from sfmkit.core.geometry import rodrigues  # noqa: E402
from sfmkit.core.metrics import align_to_reference, scale_between  # noqa: E402
from sfmkit.core.types import Matches, Pose, Reconstruction  # noqa: E402

__all__ = [
    "plot_comparison", "plot_camera_layout", "plot_track_lengths",
    "plot_matches", "plot_epipolar", "plot_residuals", "plot_dense", "render_points", "orbit",
]

OURS, THEIRS = "#2e7d32", "#1565c0"


def _scaled_centres(
    poses: dict[str, Pose], reference: str, s: float = 1.0
) -> dict[str, np.ndarray]:
    return {n: s * p.center for n, p in align_to_reference(poses, reference).items()}


def _common_scale(rec: Reconstruction, gt_poses: dict[str, Pose], reference: str) -> float:
    shared = [n for n in rec.poses if n in gt_poses and n != reference]
    if not shared:
        return 1.0
    ours = align_to_reference(rec.poses, reference)
    theirs = align_to_reference({n: gt_poses[n] for n in [reference, *shared]}, reference)
    far = max(shared, key=lambda n: np.linalg.norm(theirs[n].center))
    return scale_between(ours, theirs, far)


def plot_comparison(rec, gt_model, reference, out_path, title="Reconstruction vs COLMAP"):
    """Point clouds and cameras from four viewpoints, in a common frame and scale."""
    s = _common_scale(rec, gt_model["poses"], reference)
    ours = rec.points[rec.triangulated_mask()]
    ours = rec.poses[reference].transform(ours) if reference in rec.poses else ours

    gt_pts = gt_model["points"]
    gt_pts = gt_model["poses"][reference].transform(gt_pts) * s

    # Z-up for a readable ground plane.
    W = np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]])
    ours_v, gt_v = ours @ W.T, gt_pts @ W.T
    c_ours = {n: c @ W.T for n, c in _scaled_centres(rec.poses, reference).items()}
    c_gt = {n: c @ W.T for n, c in _scaled_centres(gt_model["poses"], reference, s).items()}

    lim = np.percentile(np.abs(np.vstack([ours_v, gt_v])), 97)
    views = [(22, -60, "Perspective"), (89, -90, "Top-down"), (2, -90, "Front"), (2, 0, "Side")]
    fig = plt.figure(figsize=(15, 12))
    for i, (elev, azim, name) in enumerate(views, 1):
        ax = fig.add_subplot(2, 2, i, projection="3d")
        ax.scatter(*gt_v.T, s=1.2, c=THEIRS, alpha=0.30, label=f"COLMAP ({len(gt_v)} pts)")
        ax.scatter(*ours_v.T, s=3.5, c=OURS, alpha=0.75, label=f"sfmkit ({len(ours_v)} pts)")
        for c in c_gt.values():
            ax.scatter(*c, s=55, marker="o", facecolors="none", edgecolors=THEIRS, linewidths=1.4)
        for n, c in c_ours.items():
            ax.scatter(*c, s=70, marker="^", color=OURS)
            if n in c_gt:
                seg = np.stack([c, c_gt[n]])
                ax.plot(*seg.T, "-", color="#c62828", lw=1.1)
        ax.view_init(elev=elev, azim=azim)
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.set_zlim(-lim, lim)
        ax.set_title(name, fontsize=10)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")
        if i == 1:
            ax.legend(loc="upper left", fontsize=8)
    fig.suptitle(f"{title}  —  aligned to {reference}, scale {s:.3f}", fontsize=13)
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return out_path


def plot_camera_layout(rec, gt_model, reference, out_path):
    """Camera positions in two orthogonal planes, with per-camera error segments."""
    s = _common_scale(rec, gt_model["poses"], reference)
    c_ours = _scaled_centres(rec.poses, reference)
    c_gt = _scaled_centres(gt_model["poses"], reference, s)

    fig, axes = plt.subplots(1, 2, figsize=(15, 7))
    for ax, (a, b, la, lb) in zip(axes, [(0, 1, "X", "Y"), (0, 2, "X", "Z")], strict=True):
        for n, c in c_gt.items():
            used = n in c_ours
            ax.scatter(c[a], c[b], s=110, marker="o",
                       facecolors=THEIRS if used else "none",
                       edgecolors=THEIRS, linewidths=1.6, zorder=3)
            ax.annotate(n, (c[a], c[b]), fontsize=8, color=THEIRS,
                        xytext=(4, 4), textcoords="offset points")
        for n, c in c_ours.items():
            ax.scatter(c[a], c[b], s=150, marker="^", color=OURS, zorder=4)
            if n in c_gt:
                ax.plot([c[a], c_gt[n][a]], [c[b], c_gt[n][b]], "-", color="#c62828", lw=1.3)
        ax.set_xlabel(la)
        ax.set_ylabel(lb)
        ax.grid(alpha=0.3)
        ax.set_aspect("equal")
        ax.set_title(f"{la}–{lb}")
    axes[0].scatter([], [], marker="o", facecolors="none", edgecolors=THEIRS,
                    label="COLMAP (not registered here)")
    axes[0].scatter([], [], marker="o", color=THEIRS, label="COLMAP")
    axes[0].scatter([], [], marker="^", color=OURS, label="sfmkit")
    axes[0].plot([], [], "-", color="#c62828", label="position error")
    axes[0].legend(fontsize=8)
    fig.suptitle(f"Camera positions  —  aligned to {reference}, scale {s:.3f}", fontsize=13)
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path


def plot_track_lengths(stats_star: dict, stats_full: dict, out_path):
    """Track-length histograms for two match graphs, side by side."""
    fig, ax = plt.subplots(figsize=(9, 5))
    keys = sorted(set(stats_star["length_histogram"]) | set(stats_full["length_histogram"]))
    x = np.arange(len(keys))
    ax.bar(x - 0.2, [stats_star["length_histogram"].get(k, 0) for k in keys],
           0.4, label=f"star graph ({stats_star['n_tracks']} tracks)", color="#9e9e9e")
    ax.bar(x + 0.2, [stats_full["length_histogram"].get(k, 0) for k in keys],
           0.4, label=f"complete graph ({stats_full['n_tracks']} tracks)", color=OURS)
    ax.set_xticks(x)
    ax.set_xticklabels(keys)
    ax.set_xlabel("track length (number of views)")
    ax.set_ylabel("tracks")
    ax.set_title("How many cameras see each 3D point")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path


def plot_matches(image0, image1, matches, out_path, max_lines: int = 400):
    """Three panels: every match, the geometric inliers, and the outliers.

    The middle and bottom panels are the useful ones: what RANSAC kept, and what
    it threw away. Outliers that form a coherent pattern usually mean a repeated
    structure in the scene rather than random mismatching.
    """
    assert isinstance(matches, Matches)
    kp0, kp1 = matches.keypoints0, matches.keypoints1
    pairs = matches.pairs
    inl = matches.inliers if matches.inliers is not None else np.ones(len(pairs), bool)

    groups = [("all matches", pairs, "#43a047"),
              ("inliers", pairs[inl], "#1e88e5"),
              ("outliers", pairs[~inl], "#e53935")]

    fig, axes = plt.subplots(len(groups), 1, figsize=(16, 4.2 * len(groups)))
    h0, w0 = image0.shape[:2]
    h1 = image1.shape[:2][0]
    canvas_h = max(h0, h1)
    for ax, (title, sel, colour) in zip(axes, groups, strict=True):
        canvas = np.zeros((canvas_h, w0 + image1.shape[1], 3), dtype=np.uint8)
        canvas[:h0, :w0] = image0 if image0.ndim == 3 else np.dstack([image0] * 3)
        canvas[:h1, w0:] = image1 if image1.ndim == 3 else np.dstack([image1] * 3)
        ax.imshow(canvas)
        step = max(1, len(sel) // max_lines)
        for i, j in sel[::step]:
            a, b = kp0[i], kp1[j]
            ax.plot([a[0], b[0] + w0], [a[1], b[1]], "-", color=colour, lw=0.35, alpha=0.55)
        ax.scatter(kp0[sel[:, 0], 0], kp0[sel[:, 0], 1], s=2, c=colour)
        ax.scatter(kp1[sel[:, 1], 0] + w0, kp1[sel[:, 1], 1], s=2, c=colour)
        ax.set_title(f"{title}: {len(sel)}", fontsize=11, loc="left")
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(f"{matches.image0} — {matches.image1}   "
                 f"({matches.n_inliers}/{matches.n_matches} inliers, "
                 f"{matches.inlier_ratio:.0%})", fontsize=13)
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
    return out_path


def plot_epipolar(image0, image1, F, points, out_path, n: int = 8, seed: int = 0):
    """Points in one image and the epipolar lines they induce in the other.

    The visual check on a fundamental matrix: every correspondence must lie on
    its line. Lines converging on a common point locate the epipole.
    """
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(points), min(n, len(points)), replace=False)
    pts = np.asarray(points)[idx]

    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(16, 6))
    ax0.imshow(image0)
    ax1.imshow(image1)
    colours = plt.cm.rainbow(np.linspace(0, 1, len(pts)))
    h, w = image1.shape[:2]
    for (x, y), c in zip(pts, colours, strict=True):
        ax0.plot(x, y, "x", color=c, markersize=11, markeredgewidth=2)
        a, b, cc = F @ np.array([x, y, 1.0])
        if abs(b) > 1e-9:
            xs = np.array([0, w])
            ax1.plot(xs, -(a * xs + cc) / b, "-", color=c, lw=1.2)
        elif abs(a) > 1e-9:
            ax1.axvline(-cc / a, color=c, lw=1.2)
    for ax, t in ((ax0, "points"), (ax1, "their epipolar lines")):
        ax.set_title(t, fontsize=11)
        ax.set_xlim(0, ax.images[0].get_array().shape[1])
        ax.set_ylim(ax.images[0].get_array().shape[0], 0)
        ax.set_xticks([])
        ax.set_yticks([])
    _ = h
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
    return out_path


def plot_residuals(image, observed, projected, out_path, title="", scale: float = 1.0):
    """Observed keypoints against where the reconstruction projects them.

    ``scale`` exaggerates the residual vectors; at a good solution they are a
    pixel or two and invisible at true size.
    """
    observed = np.asarray(observed, dtype=float)
    projected = np.asarray(projected, dtype=float)
    ok = np.isfinite(projected).all(axis=1)
    observed, projected = observed[ok], projected[ok]
    err = np.linalg.norm(observed - projected, axis=1)

    fig, ax = plt.subplots(figsize=(13, 8))
    ax.imshow(image)
    ax.scatter(observed[:, 0], observed[:, 1], s=26, marker="x",
               c="#e53935", linewidths=1.2, label="observed")
    ax.scatter(projected[:, 0], projected[:, 1], s=14, c="#1e88e5", label="projected")
    for o, p in zip(observed, projected, strict=True):
        d = (p - o) * scale
        ax.plot([o[0], o[0] + d[0]], [o[1], o[1] + d[1]], "-", color="#424242", lw=0.6)
    rmse = float(np.sqrt(np.mean(err**2))) if err.size else float("nan")
    ax.set_title(f"{title}   n={len(err)}, RMSE {rmse:.2f} px, median {np.median(err):.2f} px"
                 + (f", residuals x{scale:g}" if scale != 1 else ""), fontsize=11)
    ax.legend(loc="upper right", fontsize=9)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
    return out_path


def render_points(points, colours, K, pose: Pose, size, *, spread: int = 2,
                  background=(16, 16, 16)) -> np.ndarray:
    """The cloud as the camera at ``pose`` sees it: an image, ``(h, w, 3)`` uint8.

    A point covers ``spread`` pixels a side, and the nearest one wins them: a
    cloud has no surfaces to hide behind, so without that the back of the
    facade shows through the front.
    """
    w, h = int(size[0]), int(size[1])
    points = np.asarray(points, dtype=float)
    colours = np.asarray(colours, dtype=np.uint8)
    camera = points @ np.asarray(pose.R, dtype=float).T + np.asarray(pose.t, dtype=float)
    z = camera[:, 2]
    ahead = z > 1e-6
    uv = (camera[ahead] @ np.asarray(K, dtype=float)[:2].T) / z[ahead, None]
    x, y, depth, rgb = uv[:, 0], uv[:, 1], z[ahead], colours[ahead]

    image = np.tile(np.asarray(background, dtype=np.uint8), (h, w, 1))
    for dx in range(spread):
        for dy in range(spread):
            px = np.floor(x).astype(int) + dx
            py = np.floor(y).astype(int) + dy
            on = (px >= 0) & (px < w) & (py >= 0) & (py < h)
            # Painted back to front, so the nearest point ends up on top.
            order = np.argsort(-depth[on])
            image.reshape(-1, 3)[(py[on] * w + px[on])[order]] = rgb[on][order]
    return image


def plot_dense(points, colours, K, pose: Pose, size, out_path, *, title: str = "",
               spread: int = 2):
    """Write ``render_points``'s image, titled, as a figure."""
    image = render_points(points, colours, K, pose, size, spread=spread)
    fig, ax = plt.subplots(figsize=(image.shape[1] / 110, image.shape[0] / 110))
    ax.imshow(image)
    ax.set_xticks([])
    ax.set_yticks([])
    if title:
        ax.set_title(title, fontsize=10)
    fig.tight_layout(pad=0.2)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
    return Path(out_path)


def orbit(pose: Pose, points, degrees: float) -> Pose:
    """``pose`` swung ``degrees`` around the cloud, about the camera's own up, still looking at it.

    A second view of a cloud, from a camera that took one of the photos: enough
    to tell a facade from a flat picture of one.
    """
    points = np.asarray(points, dtype=float)
    target = np.median(points, axis=0)
    centre = np.asarray(pose.center, dtype=float)
    up = -np.asarray(pose.R, dtype=float)[1]
    swung = target + rodrigues(up * np.radians(degrees)) @ (centre - target)

    forward = target - swung
    forward /= np.linalg.norm(forward) or 1.0
    right = np.cross(forward, up)
    right /= np.linalg.norm(right) or 1.0
    R = np.stack([right, np.cross(forward, right), forward])
    return Pose(R, -R @ swung)
