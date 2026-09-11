"""Parameter sweep over the reconstruction thresholds, scored against COLMAP.

Written because the first track-based reconstruction was *worse* than the
original star-graph one despite having more points, which points at thresholds
rather than at the algorithm. Guessing which one is cheaper to test than to argue
about, so all of them are tested.
"""
import itertools
import json
import time
from pathlib import Path

import numpy as np

from sfmkit.core.metrics import compare_poses
from sfmkit.core.reconstruct import ReconstructionConfig, reconstruct
from sfmkit.core.tracks import build_tracks
from sfmkit.data import io
from sfmkit.data.colmap import read_model
from sfmkit.data.config import load_config

cfg = load_config("configs/valencia/cpu.yaml")
run = Path("runs/valencia/cpu")
files = sorted((run / "verify").glob("*.npz"))
matches = [io.load_matches(f) for f in files]
matches = [m for m in matches if cfg.localize.query not in (m.image0, m.image1)]
tracks = build_tracks(matches, min_length=cfg.sfm.min_track_length)
K = np.loadtxt(run / "calibrate" / "K.txt").reshape(3, 3)
gt = read_model(run / "colmap")["poses"]

grid = {
    "pnp_threshold": [3.0, 6.0, 12.0],
    "min_triangulation_angle_deg": [0.5, 2.0, 4.0],
    "max_reprojection_error": [3.0, 6.0, 12.0],
}
keys = list(grid)
rows = []
for combo in itertools.product(*(grid[k] for k in keys)):
    kw = dict(zip(keys, combo, strict=True))
    t0 = time.perf_counter()
    try:
        res = reconstruct(matches, K, tracks, ReconstructionConfig(
            reference=cfg.sfm.reference, seed=cfg.seed, **kw))
        rec = res.reconstruction
        cmp = compare_poses(rec.poses, gt, reference=cfg.sfm.reference)
        row = {**kw, "n_cameras": len(rec.poses), "n_points": rec.n_points,
               "mean_rot": cmp["mean_rotation_error_deg"],
               "max_rot": cmp["max_rotation_error_deg"],
               "mean_pos": cmp["mean_position_error"],
               "scale": cmp["scale"],
               "rmse": res.reports[-1].rmse_after,
               "seconds": time.perf_counter() - t0}
    except Exception as e:
        row = {**kw, "error": f"{type(e).__name__}: {e}", "seconds": time.perf_counter() - t0}
    rows.append(row)
    print(json.dumps(row), flush=True)

Path("runs/valencia/sweep.json").write_text(json.dumps(rows, indent=2))
ok = [r for r in rows if "error" not in r and r["n_cameras"] >= 9]
if ok:
    best = min(ok, key=lambda r: r["mean_rot"])
    print("\nBEST:", json.dumps(best, indent=2))
