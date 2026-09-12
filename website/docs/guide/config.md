# Configuration

One YAML file per experiment, in `configs/<project>/`. It is the whole
description of a run: the same file, the same seed and the same photographs
give the same result. Unknown keys are refused rather than ignored, so a
misspelling fails at the first stage instead of silently doing nothing.

Paths inside `calibrate.images`, `calibrate.intrinsics` and `colmap.precomputed`
are resolved against the dataset directory, so a config works wherever the data
root is mounted.

```yaml
dataset: valencia          # data/<dataset>/scene/*.jpg
name: cpu                  # the run directory; defaults to the file's name
seed: 0                    # every RANSAC and every sampler
```

## `calibrate`

Where the intrinsics come from. Exactly one of the three.

| Key | Default | |
|---|---|---|
| `images` | — | glob of chessboard photographs |
| `pattern` | `[9, 6]` | inner corners of that chessboard |
| `intrinsics` | — | path to a saved 3×3 K |
| `exif` | `false` | K from the photographs' 35 mm equivalent focal length |
| `sensor_aspect` | `[4, 3]` | the whole sensor's aspect, when the photographs are a crop of it |

```yaml
calibrate:
  exif: true               # 26 mm equivalent on a 4:3 sensor: f = 3029 px
  sensor_aspect: [4, 3]    # the phone's whole sensor; the photos are a 16:9 cut
```

!!! warning "Digital zoom"
    A phone reports the equivalent focal length of the lens, not of the crop it
    saved. A photograph taken with digital zoom therefore reads short — 17% out
    on the one photograph of this set that had it, which is why that photograph
    is no longer in it. `DigitalZoomRatio` is read and applied when the file
    records it.

## `sfm`

Matching, verification and reconstruction.

| Key | Default | |
|---|---|---|
| `images` | `[]` | the photographs to reconstruct from, without extension |
| `reference` | — | the camera the model is anchored to, and that comparisons align on |
| `max_keypoints` | `2048` | SuperPoint keypoints per photograph |
| `exhaustive` | `true` | every pair; `false` pairs each photograph with the reference only |
| `device` | `auto` | `auto`, `cpu` or `cuda` for matching |
| `ransac_threshold` | `4.0` | px, for the fundamental matrix |
| `ransac_iterations` | `1000` | |
| `min_inliers` | `20` | below this a pair is dropped |
| `min_track_length` | `2` | observations a track needs |
| `min_triangulation_angle_deg` | `1.0` | below this a point is too ill-conditioned to keep |
| `max_reprojection_error` | `8.0` | px, for filtering observations |
| `pnp_threshold` | `8.0` | px, registering a new camera |
| `min_pnp_correspondences` | `12` | below this a camera is not registered |
| `bundle_solver` | `schur` | `schur` or `scipy`: the same problem, one about 58× faster |

## `localize`

The query photograph, kept out of the reconstruction.

| Key | Default | |
|---|---|---|
| `query` | — | the photograph to place, e.g. `Img_Old` |
| `refine` | `camera` | after RANSAC: `none`, `pose`, or `camera` (K too, when K was estimated here) |

## `colmap`

The model to score against: copied, or computed.

| Key | Default | |
|---|---|---|
| `precomputed` | — | a saved model directory to copy; excludes `matches` |
| `matches` | — | `colmap` (its own features) or `sfmkit` (this run's `verify/`) |
| `camera` | `self` | `self`, COLMAP calibrates; `fixed`, it takes `calibrate`'s K |

The query always gets a camera of its own, calibrated by COLMAP with its
principal point free — a photograph a century older shares nothing with the
phone's calibration, and pinning its principal point makes COLMAP tilt the
camera instead.

## `dense`

| Key | Default | |
|---|---|---|
| `enabled` | `false` | COLMAP's dense stereo over the `colmap` model; needs CUDA |
| `max_image_size` | `2000` | photographs are scaled down to this for stereo |

## The configs in the repository

| File | What it is |
|---|---|
| `configs/valencia/cpu.yaml` | the whole pipeline on the CPU, COLMAP computed here |
| `configs/valencia/gpu-dense.yaml` | the same on a GPU, with COLMAP's dense cloud |
| `configs/valencia/no-colmap.yaml` | the CPU run scored against a saved COLMAP model, for machines without COLMAP |
