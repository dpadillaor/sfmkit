"""A finished run's live stream, written to a file instead of a broker.

    python animation-tools/record_steps.py --config projects/valencia/configs/gpu-dense.yaml \\
        --run projects/valencia/runs/reference-gpu-dense

Runs `reconstruct` again on the run's verified matches, as `growth_animation.py`
does, and keeps the messages `sfmkit reconstruct` would have published: the
`start`, a `step` per camera and the `end`, exactly as a viewer receives them.
The static demo of the viewer replays them, so its timeline can be rewound
without a broker. The reconstruction is deterministic, so the last step is the
run's saved model; the script refuses to write a stream that disagrees with it.
"""

import argparse
import json
from pathlib import Path

from sfmkit.apps.cli._common import load_K
from sfmkit.core.reconstruct import ReconstructionConfig, reconstruct
from sfmkit.core.tracks import build_tracks
from sfmkit.data import io, live
from sfmkit.data.config import load_config


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--config", required=True, help="the config the run was made with")
    p.add_argument("--run", type=Path, required=True, help="the finished run")
    p.add_argument("--out", type=Path, default=None,
                   help="default website/demo/steps/<project>/<config>.json")
    args = p.parse_args()

    cfg = load_config(args.config)
    run = args.run
    name = live.name_of(run.resolve())
    out = args.out or Path("website/demo/steps") / f"{name}.json"

    query = cfg.localize.query
    matches = [io.load_matches(f) for f in sorted((run / "verify").glob("*.npz"))]
    matches = [m for m in matches if query not in (m.image0, m.image1)]
    tracks = build_tracks(matches, min_length=cfg.sfm.min_track_length)
    s = cfg.sfm
    options = ReconstructionConfig(
        reference=s.reference, seed=cfg.seed,
        ransac_threshold=s.ransac_threshold, ransac_iterations=s.ransac_iterations,
        pnp_threshold=s.pnp_threshold,
        min_triangulation_angle_deg=s.min_triangulation_angle_deg,
        max_reprojection_error=s.max_reprojection_error,
        min_pnp_correspondences=s.min_pnp_correspondences,
        bundle_solver=s.bundle_solver,
    )

    K = load_K(run / "calibrate" / "K.txt")
    messages = [live.start_message(name, K, s.images, s.reference)]
    print(f"{name}: reconstructing from {len(matches)} pairs")
    result = reconstruct(matches, K, tracks, options,
                         on_step=lambda shot: messages.append(live.step_message(name, shot)))
    final = result.reconstruction
    messages.append(live.end_message(name, len(final.poses), final.n_points))

    saved = io.load_reconstruction(run / "reconstruct" / "reconstruction.npz")
    if (len(saved.poses), saved.n_points) != (len(final.poses), final.n_points):
        raise SystemExit(f"this is not the run's model: {len(final.poses)} cameras and "
                         f"{final.n_points} points, the run saved {len(saved.poses)} and "
                         f"{saved.n_points}")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(messages, allow_nan=False, separators=(",", ":")))
    print(f"{out}: {len(messages) - 2} steps, {out.stat().st_size / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
