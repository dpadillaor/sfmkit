"""Camera-layout comparison, zoomed to the camera cluster."""
import sys
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
DPO2 = REPO / "CV" / "DPO2"
sys.path.insert(0, str(DPO2 / "PoseEstimation")); import sfm  # noqa

RUN = Path(sys.argv[1] if len(sys.argv) > 1 else REPO / "runs/baseline-repro-01")
OUT = RUN / "figures"; REF = "Img02"; OWN_ORDER = ["Img25", "Img15", "Img23"]

def T_of(R, t):
    T = np.eye(4); T[:3,:3] = R; T[:3,3] = np.asarray(t).ravel(); return T
def C(T): return -T[:3,:3].T @ T[:3,3]
def scaled(T, s):
    R = T[:3,:3]; return T_of(R, -R @ (s * C(T)))

poses = sfm.extract_camera_poses(str(DPO2/"colmap_project/output/images.txt"))
gt = {n: T_of(p["rotation_matrix"], p["translation_vector"]) for n,p in poses.items()}
rel = lambda i: gt[i] @ np.linalg.inv(gt[REF])
with np.load(RUN/"sfm/rotations.npz") as d: R_list=[d[k] for k in d.files]
with np.load(RUN/"sfm/translations.npz") as d: t_list=[d[k] for k in d.files]
old = np.load(RUN/"sfm/old_camera.npz")
s = np.linalg.norm(C(T_of(R_list[0],t_list[0]))) / np.linalg.norm(C(rel("Img25")))

own = {"Img02": np.eye(4), **{n: T_of(R,t) for n,R,t in zip(OWN_ORDER,R_list,t_list)},
       "Img00": T_of(old["R_old_opt"], old["t_old_opt"])}
gtc = {"Img02": np.eye(4), **{n: scaled(rel(n), s) for n in gt if n != REF}}

fig, axes = plt.subplots(1, 2, figsize=(15, 7))
for ax, (a, b, la, lb) in zip(axes, [(0,1,"X","Y"), (0,2,"X","Z")]):
    for n,T in gtc.items():
        c = C(T); used = n in own
        ax.scatter(c[a], c[b], s=110, marker="o",
                   facecolors="none" if not used else "tab:blue",
                   edgecolors="tab:blue", linewidths=1.6, zorder=3)
        ax.annotate(n, (c[a], c[b]), fontsize=8, color="tab:blue",
                    xytext=(4,4), textcoords="offset points")
    for n,T in own.items():
        c = C(T)
        ax.scatter(c[a], c[b], s=150, marker="^", color="tab:green", zorder=4)
        d = C(gtc[n]) if n in gtc else None
        if d is not None:
            ax.plot([c[a], d[a]], [c[b], d[b]], "r-", lw=1.2, alpha=.8, zorder=2)
    ax.set_xlabel(la); ax.set_ylabel(lb); ax.grid(alpha=.3); ax.set_aspect("equal")
    ax.set_title(f"{la}-{lb}")
axes[0].scatter([],[],marker="o",facecolors="none",edgecolors="tab:blue",label="COLMAP (hueco = no usada por tu SfM)")
axes[0].scatter([],[],marker="o",color="tab:blue",label="COLMAP (usada)")
axes[0].scatter([],[],marker="^",color="tab:green",label="Tu SfM")
axes[0].plot([],[],"r-",label="error de posicion")
axes[0].legend(fontsize=8, loc="best")
fig.suptitle(f"Posiciones de camara: COLMAP vs SfM propio (escala {s:.3f})", fontsize=13)
fig.tight_layout(); fig.savefig(OUT/"cameras.png", dpi=140)
print("->", OUT/"cameras.png")
