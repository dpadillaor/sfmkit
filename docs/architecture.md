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

Each stage reads one directory and writes another, and every output carries a
`manifest_<stage>.json` with the config, the git commit, and package versions.

```
match        images/                 -> runs/<name>/matches/*.npz
verify       matches/                -> runs/<name>/verified/*.npz
reconstruct  verified/               -> runs/<name>/reconstruction.npz
localize     reconstruction + verified -> runs/<name>/query_pose.npz
evaluate     reconstruction + COLMAP -> runs/<name>/evaluation.json
changes      images + verified       -> runs/<name>/changes/*.png
figures      reconstruction + COLMAP -> runs/<name>/figures/*.png
```

Stage order lives in the `Makefile`, not in module names, so inserting a stage
renames nothing.

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
