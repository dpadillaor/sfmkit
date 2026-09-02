# sfmkit — Structure from Motion, and a cathedral

A small, tested Structure-from-Motion library, and the case study it was built
for: recovering the viewpoint of an undated historical photograph of the
Cathedral of Valencia by reconstructing the square from modern phone pictures
and localising the old photograph inside that reconstruction.

The reconstruction is validated against COLMAP throughout.

<!-- FIGURES -->

---

## What this is

Two things, deliberately separated:

* **`src/sfmkit/`** — a general SfM library. Two-view geometry, robust
  estimation, feature tracks, incremental reconstruction, bundle adjustment,
  visual localisation. Pure functions over numpy arrays; no file paths, no
  global state, no plotting. It knows nothing about Valencia.
* **`pipelines` (the `sfmkit` CLI) and `configs/`** — the case study. Which
  images, which thresholds, where the data lives.

The split is not cosmetic. It is what lets the whole library be tested on
synthetic scenes with exact ground truth, in seconds, with no dataset present.

## Results

Nine modern photographs (Samsung SM-G996B, 4032×2268), calibrated with OpenCV,
matched with SuperPoint + LightGlue, reconstructed and compared against a COLMAP
model of the same images.

<!-- RESULTS TABLE -->

## Quick start

```bash
pip install -e ".[dev]"
pytest                                  # 54 tests, no dataset required
```

The full pipeline, one stage at a time:

```bash
sfmkit match       --config configs/valencia_all9.yaml --out runs/all9
sfmkit verify      --config configs/valencia_all9.yaml --out runs/all9
sfmkit reconstruct --config configs/valencia_all9.yaml --out runs/all9
sfmkit localize    --config configs/valencia_all9.yaml --out runs/all9
sfmkit evaluate    --config configs/valencia_all9.yaml --out runs/all9
```

or `make all CONFIG=configs/valencia_all9.yaml`. Only `match` needs a GPU;
everything downstream runs on numpy.

## Design notes

**Every stage reads an explicit input directory and writes an explicit output
directory, and every output carries a manifest** recording the config, the git
commit and the package versions that produced it. This is the contract whose
absence is the main lesson of the project's first version (see
[docs/optimizations.md](docs/optimizations.md)).

**Randomness is always a parameter.** There is no implicit global RNG anywhere
in the library. `sfmkit localize` runs many seeds by default and reports the
pose as a distribution, because a single number from a RANSAC would be a
coin flip presented as a measurement.

**Conventions are fixed once**: points are row-major `(N, 3)` and `(N, 2)`,
poses are world-to-camera as in COLMAP, and nothing in the library performs I/O.

## Testing

```
tests/test_geometry.py      invariants + known answers + OpenCV as an oracle
tests/test_tracks.py        union-find, conflict rejection, ground-truth tracks
tests/test_robust.py        seeding, determinism, degenerate inputs
tests/test_bundle.py        packing, gauge, sparsity coverage, robust loss
tests/test_reconstruct.py   end-to-end against a synthetic scene
```

The approach worth stealing is `sfmkit.synthetic`: generate cameras and 3D
points, project them, feed the projections back through the pipeline, and assert
against the exact answer. It needs no data, runs in CI, and makes otherwise
awkward things testable — track construction, for instance, because the
generator knows which keypoints across which images are the same 3D point.

Beyond correctness, the suite pins down properties that are easy to lose:
rotations stay orthonormal, fundamental matrices stay rank 2, the declared
Jacobian sparsity pattern really does cover every nonzero, the gauge stays fixed,
and multi-view triangulation genuinely beats two-view under noise.

## History

This repository is a rewrite. The original was a set of scripts written for a
computer-vision course; it produced good geometry and no reproducibility, and
by the time it was revisited it could not be re-run at all.

[docs/optimizations.md](docs/optimizations.md) is the record of taking it apart:
what was measured, what was fixed, and — kept deliberately — the hypotheses that
were plausible, carefully argued, and wrong. The performance investigation in
particular took three wrong diagnoses before the profiler settled it, and the
wrong turns are more instructive than the answer.

## Licence

MIT.
