"""The `sfmkit figures` command."""

from __future__ import annotations

from sfmkit.apps.cli._common import console, run_dir
from sfmkit.data import io
from sfmkit.data.config import load_config


def _view(camera: dict, *, width: int):
    """A COLMAP camera's K and image size, scaled to ``width`` pixels across.

    Drawn at the photo's own size a cloud is mostly gaps; smaller, its points
    meet.
    """
    import numpy as np

    from sfmkit.data.colmap import intrinsics

    k = intrinsics(camera)
    s = width / camera["width"]
    K = np.array([[k["fx"] * s, 0, k["cx"] * s], [0, k["fy"] * s, k["cy"] * s], [0, 0, 1]])
    return K, (width, round(camera["height"] * s))


def cmd_figures(args) -> int:
    """Render the figures for a finished run: comparison, matches, residuals."""
    import cv2

    from sfmkit.core.geometry import eight_point, project
    from sfmkit.core.tracks import build_tracks, track_statistics
    from sfmkit.data.colmap import read_fused, read_model
    from sfmkit.render.viz import (
        orbit,
        plot_camera_layout,
        plot_comparison,
        plot_dense,
        plot_epipolar,
        plot_matches,
        plot_residuals,
        plot_track_lengths,
    )

    cfg = load_config(args.config)
    run = run_dir(cfg, args.out)
    rec = io.load_reconstruction(run / "reconstruct" / "reconstruction.npz")
    ref = cfg.sfm.reference or rec.registered[0]
    query = cfg.localize.query
    out = run / "figures"
    images = cfg.scene_dir
    written = []

    def read(name):
        try:
            return cv2.cvtColor(io.read_image(io.image_file(images, name)), cv2.COLOR_BGR2RGB)
        except (FileNotFoundError, OSError):
            return None

    if (run / "colmap" / "images.txt").is_file():
        model = read_model(run / "colmap")
        written += [plot_comparison(rec, model, ref, out / "comparison.png"),
                    plot_camera_layout(rec, model, ref, out / "cameras.png")]

    # The dense cloud, seen from the reference photo and from beside it: the two
    # together tell a facade from a picture of one. It is COLMAP's cloud, in
    # COLMAP's frame, so COLMAP's camera looks at it.
    dense = run / "dense" / "fused.ply"
    if dense.is_file() and (run / "colmap" / "images.txt").is_file():
        model = read_model(run / "colmap")
        if ref in model["poses"]:
            points, colours = read_fused(dense)
            camera = model["cameras"][model["image_cameras"][ref]]
            K, size = _view(camera, width=1600)
            for name, pose in (("dense", model["poses"][ref]),
                               ("dense_around", orbit(model["poses"][ref], points, 35))):
                written.append(plot_dense(points, colours, K, pose, size, out / f"{name}.png",
                                          title=f"{len(points):,} points, {ref}'s camera"))

    verified = sorted((run / "verify").glob("*.npz"))
    all_m = [io.load_matches(f) for f in verified]
    scene = [m for m in all_m if query not in (m.image0, m.image1)]
    if scene:
        star = [m for m in scene if ref in (m.image0, m.image1)]
        written.append(plot_track_lengths(
            track_statistics(build_tracks(star)),
            track_statistics(build_tracks(scene)),
            out / "tracks.png"))

    # The strongest pair, as a worked example of matching and verification.
    if all_m:
        m = max(all_m, key=lambda x: x.n_inliers)
        i0, i1 = read(m.image0), read(m.image1)
        if i0 is not None and i1 is not None:
            written.append(plot_matches(i0, i1, m, out / f"matches_{m.image0}_{m.image1}.png"))
            x0, x1 = m.points()
            if len(x0) >= 8:
                written.append(plot_epipolar(i0, i1, eight_point(x0, x1), x0,
                                             out / f"epipolar_{m.image0}_{m.image1}.png"))

    # Residuals for the reference camera, before and after the final refinement.
    kp = {}
    for mm in scene:
        kp.setdefault(mm.image0, mm.keypoints0)
        kp.setdefault(mm.image1, mm.keypoints1)
    before_path = run / "reconstruct" / "reconstruction_before_refinement.npz"
    states = [("after", rec)]
    if before_path.is_file():
        states.insert(0, ("before", io.load_reconstruction(before_path)))
    img = read(ref)
    if img is not None and ref in kp:
        for label, state in states:
            if ref not in state.poses:
                continue
            tid, kid = state.observations_of(ref)
            if not len(tid):
                continue
            written.append(plot_residuals(
                img, kp[ref][kid], project(state.points[tid], state.K, state.poses[ref]),
                out / f"residuals_{ref}_{label}.png",
                title=f"{ref}, {label} final refinement"))

    for p in written:
        console.print(f"[green]wrote[/green] {p}")
    io.write_manifest(run, "figures", cfg, config_path=args.config,
                      extra={"figures": [p.name for p in written]})
    return 0
