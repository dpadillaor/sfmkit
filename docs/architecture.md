# Architecture

For a runnable introduction to the library itself, see [tour.md](tour.md).

## Layers

```
src/sfmkit/
  core/           algorithms: arrays in, arrays out
    types.py        Pose, Matches, Track, Reconstruction
    geometry.py     two-view geometry, triangulation, projection
    robust.py       RANSAC estimators, every one taking a seed
    tracks.py       union-find over the match graph
    bundle.py       residuals, sparsity, the bundle adjustment
    reconstruct.py  incremental SfM
    localize.py     visual localisation of a query image
    changes.py      homography alignment + change detection
    metrics.py      comparison against another reconstruction
    synthetic.py    scenes with exact ground truth, for tests
  data/           everything that touches the filesystem
    io.py           run artefacts and manifests
    colmap.py       readers for COLMAP's text model
    config.py       YAML experiment configs
    features.py     SuperPoint + LightGlue (the only torch dependency)
  render/
    viz.py          figures; the only matplotlib import
  apps/           the composition root
    cli/            one module per subcommand
    tui/            terminal UI
```

Imports may only point downwards: `apps` → `render` → `data` → `core`, and
`core` imports nothing but numpy and scipy.

**This is checked, not documented.** `pyproject.toml` carries four
import-linter contracts, run by `lint-imports` in pre-commit and in CI:

| Contract | What it forbids |
|---|---|
| Layered architecture | any import pointing upwards |
| The core does no I/O and draws nothing | `core` importing matplotlib, torch, yaml, rich, textual |
| Only the render layer imports matplotlib | `core` or `data` importing matplotlib |
| Only the data layer imports torch | `core` or `render` importing torch |

Without enforcement the rule holds only for as long as everyone remembers it,
and one `import matplotlib` in `core/geometry.py` silently ends the library's
ability to be tested without a display. That is what makes the test suite
possible: `pytest` never reads a photograph, never writes a file, and never
opens a plot.

## Stage contract

A run lives in `runs/<dataset>/<config>/`. Each stage writes its own subfolder,
with a `manifest.json` holding the config, the git commit and package versions,
and reads only from the dataset and from earlier stages' subfolders.

```
calibrate    chessboard photos, or a K    -> calibrate/K.txt
match        scene photos                 -> match/*.npz
verify       match/                       -> verify/*.npz
reconstruct  verify/ + calibrate/         -> reconstruct/reconstruction.npz
localize     reconstruct/ + verify/       -> localize/query_pose.npz
colmap       a COLMAP model               -> colmap/{cameras,images,points3D}.txt
evaluate     reconstruct/ + colmap/       -> evaluate/evaluation.json
changes      scene photos + verify/       -> changes/*.png
figures      reconstruct/ + colmap/       -> figures/*.png
```

`colmap` depends on nothing but the dataset, so it could run alongside the
matching chain. Stage order lives in `apps/cli/run.py`, not in module names, so
inserting a stage renames nothing.

## Conventions

Fixed once, and enforced at module boundaries:

* **Row-major points.** 3D points are `(N, 3)`, image points `(N, 2)`. Functions
  that need column-major transpose locally and never return it.
* **World-to-camera poses**, as in COLMAP: `x_cam = R @ x_world + t`.
* **Randomness is a parameter.** No implicit global RNG anywhere in the library.
* **No I/O in the library.** Callers pass arrays.

Each of these exists because its absence caused a concrete problem in the first
version of this project: shapes were mixed freely and `.T` appeared everywhere;
pose conventions varied between functions; two RANSACs drew on an unseeded
global RNG so results could not be reproduced; and geometry functions loaded
their own inputs from hardcoded relative paths, which is why stages could not be
re-run or tested.

## Gauge

A reconstruction from images alone is determined only up to a similarity
transform. The gauge is fixed by holding the reference camera at the identity
and the first camera's baseline at unit length, parameterised by two polar
angles so the constraint is exact rather than penalised.

Comparisons against another reconstruction therefore align to a common reference
camera and resolve scale from the most distant shared camera before reporting
any error. `sfmkit.metrics.compare_poses` does this; comparing raw translations
without it is meaningless.
