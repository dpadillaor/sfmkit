"""Stage 4a: compare the custom reconstruction against COLMAP.

Replaces CV/DPO2/PoseEstimation/colmap_comparation.py, which cannot be re-run:
it reads its inputs from hardcoded paths and, worse, has the old camera pose
pasted into the source as numeric literals (colmap_comparation.py:85), so
re-running the pipeline never changes what it compares.

Those literals are still useful: they are the only surviving record of the
original stage-3 result, so they are used here as a baseline to diff against.

COLMAP poses are world->camera. The relative pose of camera i in the reference
camera's frame is T_i @ inv(T_ref); the original script wrote inv(T_ref) @ T_i,
which composes the two in the wrong order. Both are evaluated below rather than
assumed, and the one consistent with the custom reconstruction is reported.
"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
DPO2 = REPO / "CV" / "DPO2"
sys.path.insert(0, str(DPO2 / "PoseEstimation"))
import sfm  # noqa: E402

RUN = Path(sys.argv[1] if len(sys.argv) > 1 else REPO / "runs/baseline-repro-01")
SFM = RUN / "sfm"

# The old-camera pose fossilised in colmap_comparation.py:85 -- the original run's output.
BASELINE_OLD_R = np.array([[0.9862762, -0.02276854, 0.16352633],
                           [0.04625221, 0.98888959, -0.14127316],
                           [-0.1584929, 0.14689781, 0.97637136]])
BASELINE_OLD_T = np.array([-0.01835662, -0.02262854, 0.13092883])

REF = "Img02"


def T_of(R, t):
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = np.asarray(t).ravel()
    return T


def center(T):
    """Camera centre in the frame T maps from (T is world->camera)."""
    return -T[:3, :3].T @ T[:3, 3]


def rot_angle_deg(R1, R2):
    c = (np.trace(R1 @ R2.T) - 1) / 2
    return float(np.degrees(np.arccos(np.clip(c, -1, 1))))


def main():
    poses = sfm.extract_camera_poses(str(DPO2 / "colmap_project/output/images.txt"))
    gt = {n: T_of(p["rotation_matrix"], p["translation_vector"]) for n, p in poses.items()}
    print(f"COLMAP cameras: {sorted(gt)}")

    with np.load(SFM / "rotations.npz") as d:
        R_list = [d[k] for k in d.files]
    with np.load(SFM / "translations.npz") as d:
        t_list = [d[k] for k in d.files]
    old = np.load(SFM / "old_camera.npz")

    # R_list order follows the driver: [FIRST_IMAGE, *AVAILABLE_IMAGES].
    summary = json.loads((SFM / "summary.json").read_text())
    short = lambda n: n.split("_")[0]
    order = [short(summary["first_image"])] + [short(n) for n in summary["available_images"]]
    own = {n: T_of(R, t) for n, R, t in zip(order, R_list, t_list)}
    own["Img00"] = T_of(old["R_old_opt"], old["t_old_opt"])

    report = {}
    for label, rel in (("T_i @ inv(T_ref)", lambda i: gt[i] @ np.linalg.inv(gt[REF])),
                       ("inv(T_ref) @ T_i  [original]", lambda i: np.linalg.inv(gt[REF]) @ gt[i])):
        # Scale is fixed by the first pair, whose baseline was forced to norm 1.
        s = np.linalg.norm(center(own["Img25"])) / np.linalg.norm(center(rel("Img25")))
        rows = []
        for name, T_own in own.items():
            if name not in gt:
                continue
            T_gt = rel(name)
            rows.append({
                "camera": name,
                "rot_err_deg": round(rot_angle_deg(T_own[:3, :3], T_gt[:3, :3]), 3),
                "pos_err": round(float(np.linalg.norm(center(T_own) - s * center(T_gt))), 4),
                "pos_norm_own": round(float(np.linalg.norm(center(T_own))), 4),
                "pos_norm_gt_scaled": round(float(s * np.linalg.norm(center(T_gt))), 4),
            })
        mean_rot = float(np.mean([r["rot_err_deg"] for r in rows]))
        report[label] = {"scale": round(float(s), 4), "cameras": rows, "mean_rot_err_deg": round(mean_rot, 3)}
        print(f"\n=== convention: {label} ===")
        print(f"scale (own/colmap) = {s:.4f}")
        print(f"{'camera':<9}{'rot_err_deg':>13}{'pos_err':>10}{'|C|_own':>10}{'|C|_gt*s':>10}")
        for r in rows:
            print(f"{r['camera']:<9}{r['rot_err_deg']:>13.3f}{r['pos_err']:>10.4f}"
                  f"{r['pos_norm_own']:>10.4f}{r['pos_norm_gt_scaled']:>10.4f}")
        print(f"mean rotation error: {mean_rot:.3f} deg")

    d_rot = rot_angle_deg(np.asarray(old["R_old_opt"]), BASELINE_OLD_R)
    t_now = np.asarray(old["t_old_opt"]).ravel()
    report["old_camera_vs_original"] = {
        "rot_diff_deg": round(d_rot, 3),
        "t_now": t_now.tolist(),
        "t_original": BASELINE_OLD_T.tolist(),
        "t_diff_norm": round(float(np.linalg.norm(t_now - BASELINE_OLD_T)), 4),
    }
    print("\n=== old camera: this run vs the original (fossilised literals) ===")
    print(f"rotation difference : {d_rot:.3f} deg")
    print(f"t now      : {np.round(t_now, 5)}")
    print(f"t original : {np.round(BASELINE_OLD_T, 5)}")
    print(f"||dt||     : {np.linalg.norm(t_now - BASELINE_OLD_T):.4f}")

    (RUN / "compare_vs_colmap.json").write_text(json.dumps(report, indent=2))
    print(f"\nreport -> {RUN / 'compare_vs_colmap.json'}")


if __name__ == "__main__":
    main()
