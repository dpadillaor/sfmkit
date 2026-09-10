"""Generate the README results tables from run manifests.

Numbers in the README are produced from the artefacts on disk rather than typed
by hand, so they cannot drift away from what the pipeline actually did.
"""
import json
from pathlib import Path

from sfmkit.apps.tui.model import load_runs


def fmt(v, nd=3):
    return f"{v:.{nd}f}" if isinstance(v, float) else str(v)


def results_table() -> str:
    rows = []
    topo = Path("runs/valencia/experiment_topology.json")
    if topo.is_file():
        d = json.loads(topo.read_text())
        rows.append("### Star graph vs complete graph\n")
        rows.append("Identical code and thresholds; the only difference is which "
                    "image pairs the reconstruction is allowed to use.\n")
        keys = [("pairs", "verified pairs", 0), ("tracks", "tracks", 0),
                ("observations", "observations", 0),
                ("mean_track_length", "mean track length", 2),
                ("n_cameras", "cameras registered", 0), ("n_points", "3D points", 0),
                ("mean_rotation_error_deg", "mean rotation error (deg)", 3),
                ("max_rotation_error_deg", "max rotation error (deg)", 3),
                ("mean_position_error", "mean position error", 4),
                ("scale", "scale vs COLMAP", 4),
                ("final_rmse_px", "final reprojection RMSE (px)", 2),
                ("seconds", "seconds", 0)]
        rows.append("| | star (reference pairs only) | complete |")
        rows.append("|---|---|---|")
        for k, label, nd in keys:
            a, b = d["star"].get(k), d["complete"].get(k)
            rows.append(f"| {label} | {fmt(a, nd)} | {fmt(b, nd)} |")
        rows.append("")
    return "\n".join(rows)


def runs_table() -> str:
    runs = [r for r in load_runs("runs") if r.headline["cameras"] != "-"]
    if not runs:
        return ""
    out = ["### Runs\n", "| run | config | cameras | 3D points | mean rot err | scale |",
           "|---|---|---|---|---|---|"]
    for r in runs:
        h = r.headline
        out.append(f"| `{r.name}` | {r.config_name} | {h['cameras']} | {h['points']} | "
                   f"{fmt(h['mean_rot'])}° | {fmt(h['scale'], 4)} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    print(results_table())
    print(runs_table())
