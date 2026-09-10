"""Scenes with a known answer, and runs laid out as sfmkit writes them."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

K = np.array([[800.0, 0, 320], [0, 800.0, 240], [0, 0, 1]])
SIZE = (640, 480)
NAMES = ["Img02", "Img12", "Img13", "Img14"]


def rotation(axis, degrees: float) -> np.ndarray:
    """Rodrigues: a rotation of ``degrees`` about ``axis``."""
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    th = np.radians(degrees)
    A = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(th) * A + (1 - np.cos(th)) * A @ A


def world(seed: int = 0, n_points: int = 40):
    """Cameras on an arc looking at a cloud of points: ``[(name, R, t)]``, points."""
    rng = np.random.default_rng(seed)
    points = rng.normal(size=(n_points, 3)) + [0, 0, 6]
    cameras = []
    for i, name in enumerate(NAMES):
        R = rotation([0, 1, 0], -8.0 * i)
        centre = np.array([1.5 * i, 0.1 * i, 0.0])
        cameras.append((name, R, -R @ centre))
    return cameras, points


def moved(cameras, points, s: float, Rg: np.ndarray, tg: np.ndarray):
    """The same scene after the similarity X -> s Rg X + tg, as another
    reconstruction would find it."""
    out = [(n, R @ Rg.T, s * t - R @ Rg.T @ tg) for n, R, t in cameras]
    return out, points @ (s * Rg).T + tg


def quaternion(R: np.ndarray) -> np.ndarray:
    """(w, x, y, z), for a rotation with a positive trace, which ours have."""
    w = np.sqrt(1 + np.trace(R)) / 2
    return np.array([w, (R[2, 1] - R[1, 2]) / (4 * w), (R[0, 2] - R[2, 0]) / (4 * w),
                     (R[1, 0] - R[0, 1]) / (4 * w)])


def write_colmap(directory, cameras, points, colors=None) -> None:
    """A COLMAP text model, one PINHOLE camera for every image."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    (d / "cameras.txt").write_text(
        f"# Camera list\n1 PINHOLE {SIZE[0]} {SIZE[1]} {fx} {fy} {cx} {cy}\n")
    lines = ["# Image list", "#   two lines per image"]
    for i, (name, R, t) in enumerate(cameras, start=1):
        q = quaternion(R)
        lines += [f"{i} {' '.join(map(str, q))} {' '.join(map(str, t))} 1 {name}", ""]
    (d / "images.txt").write_text("\n".join(lines) + "\n")
    colors = np.full((len(points), 3), 200) if colors is None else colors
    rows = ["# 3D point list"] + [
        f"{i} {x} {y} {z} {r} {g} {b} 0.5 1 0"
        for i, ((x, y, z), (r, g, b)) in enumerate(zip(points, colors, strict=True), start=1)]
    (d / "points3D.txt").write_text("\n".join(rows) + "\n")


def write_reconstruction(path, cameras, points) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path, K=K, image_names=np.array([n for n, _, _ in cameras]),
        rotations=np.stack([R for _, R, _ in cameras]),
        translations=np.stack([t for _, _, t in cameras]), points=points,
        track_images=np.array(["[]"] * len(points)))


def write_manifest(run_dir, stage: str, timestamp: str, config: dict | None = None,
                   **extra) -> None:
    d = Path(run_dir) / stage
    d.mkdir(parents=True, exist_ok=True)
    config = config or {"sfm": {"reference": NAMES[0]}, "localize": {"query": None}}
    (d / "manifest.json").write_text(json.dumps(
        {"stage": stage, "timestamp": timestamp, "config": config, **extra}))


def make_run(root, project: str = "city", config: str = "full", *, sfmkit: bool = True,
             colmap: bool = True, dense: bool = False, evaluate: bool = True,
             timestamp: str = "2026-09-10T10:00:00+00:00", s: float = 0.5):
    """A run with sfmkit's model a similarity away from COLMAP's; its directory."""
    run = Path(root) / project / config
    theirs, points = world()
    ours, our_points = moved(theirs, points, s, rotation([1, 2, 3], 30), np.array([1.0, -2, 3]))
    write_manifest(run, "calibrate", timestamp)
    if sfmkit:
        write_reconstruction(run / "reconstruct" / "reconstruction.npz", ours, our_points)
        write_manifest(run, "reconstruct", timestamp)
    if colmap:
        write_colmap(run / "colmap", theirs, points)
        write_manifest(run, "colmap", timestamp)
    if dense:
        (run / "dense").mkdir(parents=True)
        (run / "dense" / "fused.ply").write_bytes(b"ply\nformat binary_little_endian 1.0\n")
        write_manifest(run, "dense", timestamp)
    if evaluate and sfmkit and colmap:
        (run / "evaluate").mkdir(parents=True, exist_ok=True)
        (run / "evaluate" / "evaluation.json").write_text(json.dumps(
            {"reference": NAMES[0], "scale_image": NAMES[-1], "scale": s}))
        write_manifest(run, "evaluate", timestamp, mean_rotation_error_deg=0.5,
                       max_rotation_error_deg=1.0, n_cameras=len(NAMES),
                       query_rotation_error_deg=None)
    return run
