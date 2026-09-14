# CLI reference

One command, `sfmkit`, with one subcommand per stage, plus `run`. Every
stage takes the same two options, and each stage reads what the one before it
wrote, so they can be run one at a time, re-run, or resumed.

```bash
sfmkit <stage> --config projects/<name>/configs/<config>.yaml [--out DIR]
```

| Option | Default | |
|---|---|---|
| `--config` | required | the YAML experiment file; see [Configuration](config.md) |
| `--out` | `<project>/runs/<config name>` | where the run's directories go |

There is no root to set: a config sits in `<project>/configs/`, so the project
it belongs to is where it is, and the photographs and the runs are its
neighbours. The same config therefore works on the host and inside a container
without either knowing where the other put the project. `--out` is the way to
write a run somewhere else.

## `sfmkit run`

Every stage in order, stopping at the first one that fails.

```bash
sfmkit run --config projects/valencia/configs/cpu.yaml
```

| Option | |
|---|---|
| `--from STAGE` | start there instead of at the beginning |
| `--only A,B` | those stages only, in pipeline order |
| `--skip-done` | skip any stage whose manifest already exists |
| `--trials N` | seeds for `localize` (default 20) |

`sfmkit run --help` lists the stages in the order it does them — the order
lives in `run.STAGES`, and the help is generated from it, so the two cannot
drift apart.

```bash
sfmkit run --config projects/valencia/configs/cpu.yaml --from reconstruct
sfmkit run --config projects/valencia/configs/cpu.yaml --only changes,figures
```

A stage that needs CUDA and cannot have it (`dense`) is refused before anything
runs, rather than an hour in.

## The stages

### `calibrate`

The camera's intrinsics for the run: from chessboard photographs, from a saved
3×3 matrix, or from the scene photographs' EXIF. Writes `calibrate/K.txt`.

```bash
sfmkit calibrate --config projects/valencia/configs/cpu.yaml
```

### `match`

SuperPoint keypoints and LightGlue matches for every configured pair. Writes
one `.npz` per pair, `match/ImgA__ImgB.npz`.

Features are detected on the photograph the right way up, and the keypoints are
mapped back to the stored orientation afterwards: SuperPoint is not rotation
invariant, and a phone that records "rotate me 90°" in EXIF would otherwise
produce photographs that only match each other.

The weights (53 MB) download on first use; see
[Install](../install/conda.md#the-feature-weights).

### `verify`

A fundamental matrix per pair by RANSAC, keeping the inliers. Writes the same
pair files with the verified subset, `verify/ImgA__ImgB.npz`. Pairs with fewer
than `min_inliers` survivors are dropped entirely.

### `reconstruct`

Tracks, an initial pair, then incremental registration: PnP, triangulation,
filtering and a bundle adjustment after every camera, then one global
refinement. Writes `reconstruct/reconstruction.npz` and the state from just
before that final refinement, so before-and-after is two real reconstructions
rather than one and a guess.

It publishes its progress step by step when `$SFMKIT_BROKER` names a Redis
server — [Live messages](../viewer/live.md).

### `localize`

Places the query photograph — the old one — against the finished model, and
leaves it out of the model itself so that a shaky camera cannot bend the map.
Its focal length is unknown, so a whole projection matrix is estimated by
RANSAC-DLT and decomposed, then refined in pixels under a Huber loss. Writes
`localize/query_pose.npz`.

| Option | |
|---|---|
| `--trials N` | run N seeds and report the pose as a distribution (default 20) |

### `colmap`

The model the run is scored against: COLMAP run on the same photographs, or a
saved model copied in (`colmap.precomputed`). The query is registered in a
second pass with its principal point free. Writes COLMAP's text model into
`colmap/`.

### `dense`

COLMAP's dense stereo over that model: undistort, PatchMatch, fusion. Needs an
NVIDIA GPU. Writes `dense/fused.ply`.

### `evaluate`

Compares the two reconstructions after aligning them: rotation error per
camera, position error, the scale between them, and the query's own error
reported apart. Writes `evaluate/evaluation.json`.

### `changes`

Warps the old photograph onto a modern one through a homography from the
verified matches, matches their tones, and marks what differs. Writes the
overlay, the difference and the change mask into `changes/`.

| Option | Default | |
|---|---|---|
| `--against IMAGE` | the reference | the modern photograph to compare with |
| `--threshold T` | `0.38` | dissimilarity threshold, 0 to 1 |

### `figures`

The plots for a finished run: the two reconstructions side by side, the camera
positions against COLMAP's, matches, epipolar lines, residuals, track lengths,
and the dense cloud when there is one. Writes `figures/`.

## Exit codes and errors

`0` on success, `1` on failure. Failures are reported as a line, not a
traceback: a missing file says which file, an unusable config says which key,
and missing feature weights print the URLs and the directory to put them in.
