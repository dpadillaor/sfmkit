"""Reproduce the original SuperPoint+LightGlue -> RANSAC-F baseline.

Non-destructive: reads the committed images and pair list, writes everything
under runs/<tag>/. Never touches CV/DPO2/RANSAC/results or PoseEstimation/results.

The original RANSAC used an unseeded np.random.default_rng(), so the baseline is
not bit-reproducible. We seed it here (per pair, deterministically) and validate
against the committed fundamental matrices with numerical tolerances instead.
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
DPO2 = REPO / "CV" / "DPO2"
IMAGES = DPO2 / "Images" / "Set_12MP" / "EntireSet"
BASELINE_F = DPO2 / "RANSAC" / "results" / "fundamental"

sys.path.insert(0, str(DPO2 / "RANSAC"))


def pair_list():
    """The 23 pairs the baseline actually ran, recovered from the committed F_*.txt names."""
    pairs = []
    for p in sorted(BASELINE_F.glob("F_*.txt")):
        a, b = p.stem[len("F_"):].split("_vs_")
        pairs.append((a, b))
    return pairs


def seed_for(a, b):
    """Stable per-pair seed so reruns are reproducible even though the original was not."""
    return int.from_bytes(hashlib.sha256(f"{a}_vs_{b}".encode()).digest()[:4], "big")


def stage_match(out_dir, pairs, max_keypoints=2048, max_layers=12):
    import torch
    from lightglue import LightGlue, SuperPoint
    from lightglue.utils import load_image, rbd

    torch.set_grad_enabled(False)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[match] device={device}")

    extractor = SuperPoint(max_num_keypoints=max_keypoints).eval().to(device)
    matcher = LightGlue(features="superpoint", max_layers=max_layers).eval().to(device)

    out_dir.mkdir(parents=True, exist_ok=True)
    cache = {}

    def feats(name):
        if name not in cache:
            img = load_image(IMAGES / f"{name}.jpg")
            cache[name] = extractor.extract(img.to(device))
        return cache[name]

    for a, b in pairs:
        dst = out_dir / f"{a}_vs_{b}_matches.npz"
        if dst.exists():
            print(f"[match] skip {dst.name}")
            continue
        f0, f1 = feats(a), feats(b)
        m01 = matcher({"image0": f0, "image1": f1})
        r0, r1, rm = [rbd(x) for x in [f0, f1, m01]]
        np.savez(
            dst,
            keypoints0=r0["keypoints"].cpu().numpy(),
            keypoints1=r1["keypoints"].cpu().numpy(),
            matches=rm["matches"].cpu().numpy(),
            scores=rm["scores"].cpu().numpy(),
        )
        print(f"[match] {a} vs {b}: {len(rm['matches'])} matches -> {dst.name}")


def stage_ransac(match_dir, out_dir, pairs, n_iter=1000, threshold=4):
    """Original params: nIter=1000, threshold=4 (from ransac_filter.py __main__)."""
    import sfm

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "fundamental").mkdir(exist_ok=True)
    (out_dir / "inliers").mkdir(exist_ok=True)

    real_default_rng = np.random.default_rng

    for a, b in pairs:
        src = match_dir / f"{a}_vs_{b}_matches.npz"
        data = np.load(src)
        kp0, kp1, matches = data["keypoints0"], data["keypoints1"], data["matches"]
        mk1, mk2 = kp0[matches[:, 0]], kp1[matches[:, 1]]

        h1 = np.hstack((mk1, np.ones((mk1.shape[0], 1)))).T
        h2 = np.hstack((mk2, np.ones((mk2.shape[0], 1)))).T

        # Seed the unseeded rng inside sfm.ransac_fundamental_matrix.
        seed = seed_for(a, b)
        np.random.default_rng = lambda *_a, **_k: real_default_rng(seed)
        try:
            F, inliers = sfm.ransac_fundamental_matrix(
                h1, h2, image1=None, image2=None, nIter=n_iter, threshold=threshold
            )
        finally:
            np.random.default_rng = real_default_rng

        np.savetxt(out_dir / "fundamental" / f"F_{a}_vs_{b}.txt", F)
        np.savez(
            out_dir / "inliers" / f"{a}_vs_{b}_inliers.npz",
            keypoints0=kp0, keypoints1=kp1, matches=matches,
            inliers_matches=matches[inliers],
        )
        print(f"[ransac] {a} vs {b}: {int(inliers.sum())}/{len(matches)} inliers")


def sym_epipolar_error(F, x1h, x2h):
    """Mean symmetric epipolar distance for homogeneous 3xN correspondences."""
    l2 = F @ x1h
    l1 = F.T @ x2h
    d2 = np.abs(np.sum(x2h * l2, axis=0)) / np.linalg.norm(l2[:2], axis=0)
    d1 = np.abs(np.sum(x1h * l1, axis=0)) / np.linalg.norm(l1[:2], axis=0)
    return float(np.mean((d1 + d2) / 2))


def normalize_F(F):
    F = F / np.linalg.norm(F)
    # Fundamental matrices are defined up to sign; pin it via the largest-|value| entry.
    return F * np.sign(F.flat[np.argmax(np.abs(F))])


def stage_compare(new_dir, match_dir, pairs, report_path):
    rows = []
    for a, b in pairs:
        F_new = np.loadtxt(new_dir / "fundamental" / f"F_{a}_vs_{b}.txt")
        F_base = np.loadtxt(BASELINE_F / f"F_{a}_vs_{b}.txt")

        data = np.load(match_dir / f"{a}_vs_{b}_matches.npz")
        kp0, kp1, matches = data["keypoints0"], data["keypoints1"], data["matches"]
        mk1, mk2 = kp0[matches[:, 0]], kp1[matches[:, 1]]
        h1 = np.hstack((mk1, np.ones((len(mk1), 1)))).T
        h2 = np.hstack((mk2, np.ones((len(mk2), 1)))).T

        inl = np.load(new_dir / "inliers" / f"{a}_vs_{b}_inliers.npz")["inliers_matches"]
        rows.append({
            "pair": f"{a}_vs_{b}",
            "n_matches": int(len(matches)),
            "n_inliers": int(len(inl)),
            "inlier_ratio": round(len(inl) / max(len(matches), 1), 4),
            "err_new": round(sym_epipolar_error(normalize_F(F_new), h1, h2), 4),
            "err_baseline": round(sym_epipolar_error(normalize_F(F_base), h1, h2), 4),
            "frob_dist": round(float(np.linalg.norm(normalize_F(F_new) - normalize_F(F_base))), 4),
        })

    report_path.write_text(json.dumps(rows, indent=2))
    hdr = f"{'pair':<34}{'match':>7}{'inl':>7}{'ratio':>8}{'err_new':>10}{'err_base':>10}{'frob':>8}"
    print("\n" + hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['pair']:<34}{r['n_matches']:>7}{r['n_inliers']:>7}{r['inlier_ratio']:>8.3f}"
              f"{r['err_new']:>10.3f}{r['err_baseline']:>10.3f}{r['frob_dist']:>8.3f}")
    print(f"\nreport -> {report_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=time.strftime("baseline-%Y%m%d-%H%M%S"))
    ap.add_argument("--stages", default="match,ransac,compare")
    ap.add_argument("--threshold", type=float, default=4)
    ap.add_argument("--n-iter", type=int, default=1000)
    args = ap.parse_args()

    run = REPO / "runs" / args.tag
    match_dir, ransac_dir = run / "matches", run / "ransac"
    pairs = pair_list()
    print(f"run={run}\npairs={len(pairs)}")

    stages = args.stages.split(",")
    if "match" in stages:
        stage_match(match_dir, pairs)
    if "ransac" in stages:
        stage_ransac(match_dir, ransac_dir, pairs, args.n_iter, args.threshold)
    if "compare" in stages:
        run.mkdir(parents=True, exist_ok=True)
        stage_compare(ransac_dir, match_dir, pairs, run / "compare_vs_baseline.json")


if __name__ == "__main__":
    main()
