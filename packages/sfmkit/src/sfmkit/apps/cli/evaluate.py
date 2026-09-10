"""The `sfmkit evaluate` command."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from rich.table import Table

from sfmkit.apps.cli._common import console, load_K, run_dir
from sfmkit.core.metrics import compare_camera, compare_poses
from sfmkit.core.types import Pose
from sfmkit.data import io
from sfmkit.data.colmap import intrinsics, read_model
from sfmkit.data.config import load_config


def cmd_evaluate(args) -> int:
    """Compare the reconstruction, and the localised query, against the run's COLMAP."""
    cfg = load_config(args.config)
    run = run_dir(cfg, args.out)
    rec = io.load_reconstruction(run / "reconstruct" / "reconstruction.npz")
    colmap = run / "colmap"
    if not (colmap / "images.txt").is_file():
        console.print(f"[red]no COLMAP model in {colmap}[/red] -- run `sfmkit colmap` first")
        return 1
    model = read_model(colmap)

    ref = cfg.sfm.reference or rec.registered[0]
    cmp = compare_poses(rec.poses, model["poses"], reference=ref)
    _print_cameras(cmp)
    query = _query(cfg.localize.query, run, rec.poses, model, cmp)
    cameras = _intrinsics(run, model, ref, cfg.localize.query)
    _print_intrinsics(cameras)

    out = run / "evaluate"
    out.mkdir(parents=True, exist_ok=True)
    result = {**cmp, "query": query, "intrinsics": cameras}
    (out / "evaluation.json").write_text(json.dumps(result, indent=2, default=float))
    io.write_manifest(run, "evaluate", cfg, config_path=args.config, extra={
        "mean_rotation_error_deg": cmp["mean_rotation_error_deg"],
        "max_rotation_error_deg": cmp["max_rotation_error_deg"],
        "scale": cmp["scale"], "n_cameras": cmp["n_cameras"],
        "query_rotation_error_deg": query["rotation_error_deg"] if query else None,
        "query_position_error": query["position_error"] if query else None,
    })
    return 0


def _query(name: str | None, run: Path, poses: dict[str, Pose], model: dict, cmp: dict):
    """The localised query against COLMAP's, scored apart from the other cameras."""
    pose_file = run / "localize" / "query_pose.npz"
    if not name or not pose_file.is_file():
        return None
    if name not in model["poses"]:
        console.print(f"[yellow]{name} is not in COLMAP's model: its localisation is not scored")
        return None
    q = np.load(pose_file)
    row = compare_camera({**poses, name: Pose(q["R"], q["t"])}, model["poses"], name,
                         cmp["reference"], cmp["scale_image"])
    console.print(f"{name} (localised, not in the means): rotation err "
                  f"[bold]{row['rotation_error_deg']:.3f}°[/bold], position err "
                  f"{row['position_error']:.4f}")
    return row


def _intrinsics(run: Path, model: dict, ref: str, query: str | None) -> dict:
    """The K sfmkit used or estimated, beside COLMAP's, for the scene and the query."""
    def ours(K):
        return None if K is None else {"fx": K[0, 0], "fy": K[1, 1], "cx": K[0, 2], "cy": K[1, 2]}

    def theirs(image):
        camera = model["image_cameras"].get(image)
        return None if camera is None else intrinsics(model["cameras"][camera])

    out = {ref: {"sfmkit": ours(load_K(run / "calibrate" / "K.txt")), "colmap": theirs(ref)}}
    pose_file = run / "localize" / "query_pose.npz"
    if query and pose_file.is_file():
        q = np.load(pose_file)
        out[query] = {"sfmkit": ours(q["K"] if "K" in q.files else None), "colmap": theirs(query)}
    return out


def _print_cameras(cmp: dict) -> None:
    table = Table(title=f"vs COLMAP  (scale {cmp['scale']:.4f}, reference {cmp['reference']})")
    for c, j in (("camera", "left"), ("rotation err (deg)", "right"),
                 ("position err", "right"), ("dist. from ref", "right")):
        table.add_column(c, justify=j)
    for r in cmp["cameras"]:
        table.add_row(r["camera"], f"{r['rotation_error_deg']:.3f}",
                      f"{r['position_error']:.4f}", f"{r['distance_from_reference']:.3f}")
    console.print(table)
    console.print(f"mean rotation error [bold]{cmp['mean_rotation_error_deg']:.3f}°[/bold], "
                  f"max {cmp['max_rotation_error_deg']:.3f}°, "
                  f"{cmp['n_cameras']} shared cameras")


def _print_intrinsics(cameras: dict) -> None:
    def f(k):
        return "-" if k is None else f"{k['fx']:.0f}, {k['fy']:.0f}"

    def c(k):
        return "-" if k is None else f"{k['cx']:.0f}, {k['cy']:.0f}"

    table = Table(title="intrinsics: focal lengths f and principal point c, in pixels")
    for column in ("camera of", "sfmkit f", "sfmkit c", "COLMAP f", "COLMAP c"):
        table.add_column(column, justify="left" if column == "camera of" else "right")
    for image, k in cameras.items():
        table.add_row(image, f(k["sfmkit"]), c(k["sfmkit"]), f(k["colmap"]), c(k["colmap"]))
    console.print(table)
