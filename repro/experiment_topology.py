"""Star graph versus complete graph, on the real dataset.

The original pipeline only ever consumed pairs involving the reference image.
This runs the same reconstruction code over both match sets so that the only
difference is the topology of the graph, and reports what that costs.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, "src")
from sfmkit.data import io
from sfmkit.data.colmap import read_model
from sfmkit.data.config import load_config
from sfmkit.core.metrics import compare_poses
from sfmkit.core.reconstruct import ReconstructionConfig, reconstruct
from sfmkit.core.tracks import build_tracks, track_statistics

cfg = load_config("configs/valencia_all9.yaml")
K = np.loadtxt(cfg.intrinsics).reshape(3, 3)
gt = read_model(cfg.colmap_model)["poses"]
ref = cfg.reference

allm = [io.load_matches(f) for f in sorted(Path("runs/kit-all9/verified").glob("*.npz"))]
allm = [m for m in allm if cfg.query not in (m.image0, m.image1)]
star = [m for m in allm if ref in (m.image0, m.image1)]

out = {}
for label, ms in (("star", star), ("complete", allm)):
    tracks = build_tracks(ms, min_length=cfg.min_track_length)
    stats = track_statistics(tracks)
    t0 = time.perf_counter()
    res = reconstruct(ms, K, tracks, ReconstructionConfig(reference=ref, seed=cfg.seed))
    rec = res.reconstruction
    cmp = compare_poses(rec.poses, gt, reference=ref)
    out[label] = {
        "pairs": len(ms),
        "tracks": stats["n_tracks"],
        "observations": sum(t.length for t in tracks),
        "mean_track_length": round(stats["mean_length"], 2),
        "max_track_length": stats["max_length"],
        "n_cameras": len(rec.poses),
        "n_points": rec.n_points,
        "mean_rotation_error_deg": round(cmp["mean_rotation_error_deg"], 3),
        "max_rotation_error_deg": round(cmp["max_rotation_error_deg"], 3),
        "mean_position_error": round(cmp["mean_position_error"], 4),
        "scale": round(cmp["scale"], 4),
        "final_rmse_px": round(res.reports[-1].rmse_after, 3),
        "seconds": round(time.perf_counter() - t0, 1),
        "per_camera": {c["camera"]: round(c["rotation_error_deg"], 3) for c in cmp["cameras"]},
    }
    print(f"{label}: {json.dumps({k: v for k, v in out[label].items() if k != 'per_camera'})}", flush=True)

Path("runs/experiment_topology.json").write_text(json.dumps(out, indent=2))

hdr = f"{'':28}{'STAR':>12}{'COMPLETE':>12}"
print("\n" + hdr); print("-" * len(hdr))
for k in ("pairs", "tracks", "observations", "mean_track_length", "max_track_length",
          "n_cameras", "n_points", "mean_rotation_error_deg", "max_rotation_error_deg",
          "mean_position_error", "scale", "final_rmse_px", "seconds"):
    print(f"{k:28}{out['star'][k]:>12}{out['complete'][k]:>12}")
