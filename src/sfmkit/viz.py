"""Figures. The only module that imports matplotlib.

Kept apart from the library proper so that nothing in the reconstruction path
can accidentally open a plot window -- the original scripts were unrunnable
headless because ``plt.show()`` was scattered through the geometry code.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from sfmkit.metrics import align_to_reference, scale_between  # noqa: E402
from sfmkit.types import Pose, Reconstruction  # noqa: E402

__all__ = ["plot_comparison", "plot_camera_layout", "plot_track_lengths"]

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
