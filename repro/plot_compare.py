"""Render the COLMAP vs custom-reconstruction comparison (presentation slides 35-38).

Both are expressed in the reference camera's frame and COLMAP is scaled by the
factor implied by the first pair, whose baseline the pipeline forced to norm 1.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
DPO2 = REPO / "CV" / "DPO2"
sys.path.insert(0, str(DPO2 / "PoseEstimation"))
import sfm  # noqa: E402

RUN = Path(sys.argv[1] if len(sys.argv) > 1 else REPO / "runs/baseline-repro-01")
OUT = RUN / "figures"; OUT.mkdir(parents=True, exist_ok=True)
REF, OWN_ORDER = "Img02", ["Img25", "Img15", "Img23"]

# Z-up view transform used by the original scripts.
T_w1 = np.array([[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]]).T


def T_of(R, t):
    T = np.eye(4); T[:3, :3] = R; T[:3, 3] = np.asarray(t).ravel(); return T


def center(T):
    return -T[:3, :3].T @ T[:3, 3]


def scaled(T, s):
    """Scale a world->camera pose by moving its centre, keeping its rotation."""
    R = T[:3, :3]
    return T_of(R, -R @ (s * center(T)))


poses = sfm.extract_camera_poses(str(DPO2 / "colmap_project/output/images.txt"))
gt = {n: T_of(p["rotation_matrix"], p["translation_vector"]) for n, p in poses.items()}
rel = lambda i: gt[i] @ np.linalg.inv(gt[REF])

with np.load(RUN / "sfm/rotations.npz") as d: R_list = [d[k] for k in d.files]
with np.load(RUN / "sfm/translations.npz") as d: t_list = [d[k] for k in d.files]
own_pts = np.load(RUN / "sfm/3D_points.npy")
old = np.load(RUN / "sfm/old_camera.npz")

s = np.linalg.norm(center(T_of(R_list[0], t_list[0]))) / np.linalg.norm(center(rel("Img25")))
print(f"scale = {s:.4f}")

# COLMAP points -> reference frame, scaled.
cp = sfm.load_points_from_colmap(str(DPO2 / "colmap_project/output/points3D.txt"))
cp_h = np.vstack([cp.T, np.ones(cp.shape[0])])
gt_pts = (gt[REF] @ cp_h)[:3].T * s

own_h = np.vstack([own_pts.T, np.ones(own_pts.shape[0])])
own_v = (T_w1 @ own_h)[:3].T
gt_v = (T_w1 @ np.vstack([gt_pts.T, np.ones(len(gt_pts))]))[:3].T

own_cams = {"REF": np.eye(4), **{n: T_of(R, t) for n, R, t in zip(OWN_ORDER, R_list, t_list)}}
own_cams["OLD"] = T_of(old["R_old_opt"], old["t_old_opt"])
gt_cams = {"REF": np.eye(4), **{n: scaled(rel(n), s) for n in gt if n != REF}}


def draw(ax, pts_gt, pts_own, elev, azim, title, cams=True):
    ax.scatter(*gt_v.T, s=1.5, c="tab:blue", alpha=.35, label=f"COLMAP ({len(gt_v)} pts)")
    ax.scatter(*own_v.T, s=4, c="tab:green", alpha=.8, label=f"Own ({len(own_v)} pts)")
    if cams:
        for n, T in gt_cams.items():
            sfm.drawRefSystem(ax, T_w1 @ np.linalg.inv(T), "-", "")
        for n, T in own_cams.items():
            C = (T_w1 @ np.linalg.inv(T))[:3, 3]
            ax.scatter(*C, s=70, c="red", marker="^", zorder=10)
            ax.text(*C, f" {n}", fontsize=7, color="darkred")
    ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z")
    ax.set_title(title, fontsize=10)


lim = np.percentile(np.abs(np.vstack([own_v, gt_v])), 97)
views = [(22, -60, "Perspective"), (89, -90, "Top-down (vs Google Earth)"),
         (0, -90, "Front"), (0, 0, "Side")]
fig = plt.figure(figsize=(15, 12))
for i, (el, az, t) in enumerate(views, 1):
    ax = fig.add_subplot(2, 2, i, projection="3d")
    draw(ax, gt_v, own_v, el, az, t)
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim); ax.set_zlim(-lim, lim)
    if i == 1:
        ax.legend(loc="upper left", fontsize=8)
fig.suptitle(f"COLMAP (blue) vs custom SfM (green) -- aligned to {REF}, scale {s:.3f}", fontsize=13)
fig.tight_layout()
fig.savefig(OUT / "colmap_vs_own.png", dpi=130)
print(f"-> {OUT/'colmap_vs_own.png'}")

# Top-down only, larger, cameras labelled: the view that maps onto the square.
fig2 = plt.figure(figsize=(11, 9))
ax = fig2.add_subplot(111, projection="3d")
draw(ax, gt_v, own_v, 89, -90, "Top-down: camera layout on the cathedral square")
ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim); ax.set_zlim(-lim, lim)
ax.legend(loc="upper left", fontsize=9)
fig2.tight_layout(); fig2.savefig(OUT / "topdown.png", dpi=130)
print(f"-> {OUT/'topdown.png'}")
