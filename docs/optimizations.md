# Optimisation notes

Findings from reproducing the original pipeline on a clean machine
(2026-09-02). Nothing here has been applied — the baseline is deliberately
untouched so that any change can be measured against it.

Every number tagged **measured** comes from `runs/baseline-repro-01/`. Numbers
tagged **estimated** are derived from reading the code and should be confirmed
with a profiler before anyone spends effort on them.

---

## 0. The structural problem: no contract between stages

This matters more than any speed-up, because it is why the repository arrived
with no final results at all.

Each script assumes the previous one left something in a particular place,
nothing verifies it, and when a file turns out to be missing the gap gets
patched by hand. Four instances of the same root cause:

- `prueba.py` computes the old camera pose — `R_old_opt`, `t_old_opt`, `K_old`,
  the actual deliverable of the project — and only plots it. Nothing is saved.
- The save block at `prueba.py:388-399` is commented out, so `rotations.npz` and
  `translations.npz` were never written.
- `colmap_comparation.py:85` therefore cannot load the old camera pose, and has
  the nine numbers **pasted into the source as literals**. Re-running the whole
  pipeline does not change what that script compares: the data flow is severed,
  not merely misrouted.
- `export_keypoints_to_colmap` / `export_matches_to_colmap` — the bridge to
  COLMAP — exist only inside `RANSAC/ransac_filter.ipynb`, in no `.py` file.

An accidental silver lining: those hardcoded literals are the only surviving
record of the original stage-3 output, and can serve as the baseline to validate
a re-run against.

The fix is not cosmetic. Every stage should read from an explicit input
directory and write to an explicit output directory, with no result values
living in source code. Without that, correctness of the algorithm is irrelevant
— the pipeline cannot be re-run.

---

## 1. Bundle adjustment performance

There turned out to be **two independent problems** superimposed. Separating them
took three wrong hypotheses; both the answers and the wrong turns are recorded
below, because the wrong turns are the transferable part.

### 1.0 Problem A: a slow SVD that has nothing to do with this code

`least_squares(method='trf')` with a dense Jacobian solves each trust-region
subproblem via `scipy.linalg.svd` (`trf.py`, the `tr_solver == 'exact'` branch).
cProfile put **98.4 %** of the 337 s BA there: 2 calls, 72.8 s each.

That SVD is pathologically slow *in this environment*, and the matrix has nothing
to do with it — a random matrix of the same shape takes just as long:

```
svd 2524x1766      numpy.linalg.svd    1.16 s
                   scipy.linalg.svd   78.62 s     <- 68x
svd 1200x900       numpy.linalg.svd    0.25 s
                   scipy.linalg.svd   21.54 s     <- 86x
                   numpy, 1 thread     0.40 s     <- not a threading issue
```

Both link OpenBLAS with 24 threads, but different builds (numpy 0.3.23, scipy
0.3.27). Substituting numpy's SVD into scipy's solver, changing nothing else:

```
BA original (scipy svd)        : 336.8 s   nfev=6   cost=2.763900e+03
BA original + numpy.linalg.svd :   8.7 s   nfev=6   cost=2.763941e+03
```

**38x, with no algorithmic change.** This is an environment defect, not a code
defect, and it accounted for almost all of the original runtime. The precise
root cause (OpenBLAS build vs. how scipy queries the `gesdd` workspace) was not
isolated further.

### 1.1 Problem B: the dense solve does not scale

Independently of A, the `exact` path is O(n^3) in the parameter count. Measured
on real BA inputs dumped from the reconstruction, with problem A already fixed
on the dense side:

| Params | Cameras | Dense + numpy SVD | `jac_sparsity` + `lsmr` | Factor |
|---|---|---|---|---|
| 1766 | 4 | **8.7 s** | 10.8 s | 0.81x |
| ~2900 | 7 | 65.9 s | **8.1 s** | 8.1x |
| 3128 | 8 | 63.7 s | **11.5 s** | 5.5x |
| 3170 | 9 | 120.6 s | **16.4 s** | **7.4x** |

Final costs agree to within 0.08 % throughout.

**There is a crossover.** At 4 cameras the dense path wins by 24 %; from ~7
cameras the sparse path wins by 5-8x, and the gap widens as n^3.

The BA Jacobian is 99.7 % zeros (14 734 non-zeros in 2524x1766). `jac_sparsity`
colours the columns — 1766 finite-difference evaluations become 10 — and forces
`tr_solver='lsmr'`, which never forms the SVD at all. Note that the two fixes are
**not composable**: they live on mutually exclusive branches, so the sparse path
was never affected by problem A, which makes the comparison above fair.

Prototyped in `repro/fastba.py`, driven by `repro/stage23_fast.py` (both in the history before commit c665df5); the library version is `sfmkit.core.bundle`.

### 1.2 Three hypotheses that were wrong

**"The residual function dominates."** Reasoning from the code suggested 1766
finite-difference evaluations per Jacobian over a Python loop that rebuilds
visibility on every call (`sfm.py:727`) had to be the cost. Predicted 99.3 %
residual / 0.7 % solver; cProfile measured **1.5 % / 98.4 %** — exactly
inverted. The initial estimate benchmarked `svd` on a *random* matrix (0.93 s)
rather than the real one (72.8 s), and mistook a library difference for a data
difference.

**"Denormal numbers are stalling the SVD."** Refuted directly: the Jacobian has
0 denormals, 0 NaN/Inf, and a dynamic range of only 1.8e5. Flushing tiny values
to zero changed nothing (75.8 s to 77.4 s).

**"`crossMatrix`'s `dtype='object'` poisons the chain."** `crossMatrix`
(`sfm.py:659`) does build its 3x3 as object dtype, but `expm` returns float64 and
the residual vector is float64. No propagation.

Optimising the residual anyway (Rodrigues in closed form instead of
`expm(crossMatrix(.))`, hoisting the visibility indices) gives a **9x** faster
residual, 0.61 ms to 0.068 ms — worth ~1.5 % of runtime. It is kept in
`fastba.py` because it was nearly free, not because it mattered.

**Verified equivalent, not merely similar:** Rodrigues vs `expm(crossMatrix(.))`
agrees to 9e-16; the full residual on real BA inputs to 1.2e-14 relative.

### 1.3 Analytic Jacobian — the largest remaining lever

After 1.1 the linear algebra is no longer the cost; the **iteration count** is.
`lsmr` takes approximate steps and needs far more of them: `nfev` 1185, 1424 and
1862 on the 7-, 8- and 9-camera problems, against 6-10 for the exact path. And
each Jacobian is still estimated by finite differences (10 grouped evaluations).

Closed-form derivatives of the reprojection residual w.r.t. pose and point give
exact search directions (fewer iterations) at one pass instead of ten. This is
what g2o and Ceres do, and unlike 1.0 and 1.1 it **composes** with the sparsity
pattern.

Cheaper alternative with most of the benefit: express the residual in PyTorch and
let autograd produce the derivatives. The win is automatic differentiation, not
the GPU (see section 4).

### 1.4 Sparse Schur complement

Marginalise the points (block-diagonal, 3x3 inverses) and solve a small
camera-only system — 54x54 with 9 cameras.

This is the combination the other two fixes cannot express: **sparse structure
plus dense numpy algebra**, avoiding both the huge SVD and `lsmr`'s ~1800
iterations. SciPy's `least_squares` cannot be configured this way; it means
writing the Levenberg-Marquardt loop.

Worth doing only if 1.3 proves insufficient. For a computer-vision portfolio it
also carries weight on its own: the Schur complement is *the* idea that makes
bundle adjustment tractable.

### 1.5 What the speed-up actually bought — and what it did not

`prueba.py:20` reconstructed from **4 cameras**, with four more commented out on
the line below. **Measured:** those three BAs took ~790 s; adding the rest was
estimated at over an hour, which is why they were commented out. After 1.1, a
**9-camera** reconstruction runs its eight BAs in **283 s**.

So the fix bought the experiment. What the experiment showed was not what was
expected:

| Run | Cameras | 3D points | Mean rot. err vs COLMAP | Max |
|---|---|---|---|---|
| Original set | 4 | 675 | **0.65 deg** | 1.16 deg |
| COLMAP's set | 9 | 1041 | 0.96 deg | 2.77 deg |
| + Img16 | 10 | 1041 | 0.97 deg | 2.83 deg |

**More cameras did not improve accuracy — it slightly degraded it.** Coverage and
point count improved (the camera baseline more than doubled, reaching the far
viewpoints Img12 and Img28), but per-camera error rose.

The prediction that a wider baseline would close much of the gap with COLMAP was
wrong. The limiting factor is not the number of cameras: it is the topology of
the pose graph (section 4). A wider baseline does not help when every camera is
tied to the reference and to nothing else.


### 1.6 Threshold calibration by grid search

The reconstruction thresholds were chosen by exhaustive search over 27
combinations, each scored against COLMAP (`scripts/sweep.py`), rather than by
intuition. This moved the mean rotation error further than any structural
change in this document: **1.603 -> 0.981 degrees**, and `Img12` from 7.20 to
2.84.

Only 8 of 27 combinations register all nine cameras. The best:

| pnp | angle | reproj | cameras | points | mean rot | max rot |
|---|---|---|---|---|---|---|
| 6.0 | 2.0 | 12.0 | 9 | 1701 | **1.057** | 3.046 |
| 12.0 | 4.0 | 12.0 | 9 | 1428 | **1.293** | 2.405 |
| 12.0 | 2.0 | 6.0 | 9 | 1089 | **1.517** | 3.766 |
| 12.0 | 2.0 | 3.0 | 9 | 596 | **1.562** | 3.755 |
| 6.0 | 4.0 | 12.0 | 9 | 1350 | **1.652** | 4.773 |
| 12.0 | 4.0 | 6.0 | 9 | 863 | **1.707** | 3.676 |
| 12.0 | 2.0 | 12.0 | 9 | 1542 | **2.107** | 7.666 |
| 6.0 | 2.0 | 6.0 | 9 | 983 | **3.308** | 15.223 |

Two results run against intuition and are the reason this was searched rather
than guessed:

Mean cameras registered, averaged across the grid:

| threshold | | | |
|---|---|---|---|
| `max_reprojection_error` | 3.0 -> **6.0** | 6.0 -> **7.3** | 12.0 -> **7.7** |
| `min_triangulation_angle_deg` | 0.5 -> **6.0** | 2.0 -> **7.9** | 4.0 -> **7.1** |
| `pnp_threshold` | 3.0 -> **4.9** | 6.0 -> **7.7** | 12.0 -> **8.4** |

**A tighter reprojection threshold is worse, not safer.** Discarding a point
because it does not yet fit also discards the correspondence a later bundle
adjustment would have used to pull it into line, and the next camera is left
without enough to register against. At 3.0 px only 6 cameras register on
average; at 12.0 px, 7.7.

**The triangulation angle is not monotonic**, which is the more interesting
result. Raising it from 0.5 to 2.0 degrees *increases* cameras registered from
6.0 to 7.9 -- points triangulated from near-parallel rays have badly conditioned
depth, and admitting them corrupts the PnP of every camera that later relies on
them. Raising it further to 4.0 drops back to 7.1: now genuinely useful points
are being refused. There is an optimum, and it is not at either end.

**A looser PnP threshold registers more cameras but not better ones.** 12.0
averages 8.4 cameras against 6.0's 7.7, yet the best configuration uses 6.0 --
the extra registrations it admits are poor ones.

The first two are instances of the same thing: in an incremental pipeline, the
cost of a decision is paid by the stages downstream of it, not where it is made.
That is what makes these thresholds impossible to set by local reasoning, and
worth the hour of compute to search.

---

## 2. RANSAC

`sfm.py:132` (and the divergent copy at `RANSAC/sfm.py:103`) loops 1000 times in
Python, each iteration sampling 8 points and running an SVD.

**The 1000 hypotheses are fully independent**, which makes this the one place in
the pipeline where a GPU genuinely pays. `torch.linalg.svd` accepts batches: a
`(1000, 8, 9)` tensor solves all of them at once, and scoring the hypotheses is a
matmul plus a sum. The Python loop collapses into a handful of operations.

**Measured** on the RTX 4090, 1000 SVDs of 8x9:

| | Time |
|---|---|
| CPU, Python loop of 1000 | 12.0 ms |
| GPU, all 1000 batched | **0.5 ms** |

**24x**, and it applies across all 23+ pairs. float32 is fine here — the result
only ranks hypotheses by inlier count, it is not a conditioning-sensitive solve
(contrast the BA, section 5).

**Two unseeded RANSACs**, and the second one matters more than it looks:

- `sfm.py:131` — `rng = np.random.default_rng()`, unseeded. The reproduction
  harness patches a per-pair seed in from outside; it belongs as a `seed=None`
  parameter.
- `sfm.py:1041` — `ransac_dlt` uses `sample(range(num_points), 6)` from Python's
  `random`, unseeded. This estimates the **old camera pose, the deliverable of
  the whole project**.

The consequence is measured, not theoretical. Four runs of the same problem gave
old-camera rotation errors of **12.1, 26.5, 31.1 and 5.5 degrees** against COLMAP.
Those are not four reconstructions — they are four dice rolls. Stage 3 is not
reproducible at all, and its run-to-run variance dwarfs any difference between
implementations, so comparing single values there is meaningless.

This also explains the presentation's complaint that the old camera is "rotated a
little bit weird" (slide 28), which was attributed to a skewed K. It was a bad
draw from a 6-point RANSAC over ~200 correspondences on a 557x418 photo.

**It should be reported as a distribution** — N seeds, median and interval — not
as a single number.

The cheapest fix for stage 3 is to drop the hand-rolled `ransac_dlt` for
`cv2.solvePnPRansac`, which is far better tested, and pin `cv2.setRNGSeed()`.
That removes both the variance and a piece of untested custom code in one move
(section 6).

Also: `sfm.py:156` — `best_inliers` is read but only assigned inside
`if inliers_count > best_inliers_count`. If no sample ever improves on the
initial count, this raises `UnboundLocalError`.

---

## 3. Pair quality gating — hypothesis tested and refuted

Pair `Img02-Img16` yields 27 inliers from 130 matches (ratio 0.21) with 14 px
mean epipolar error, by far the worst of the 23. COLMAP rejects `Img16` outright:
it registers 10 of 11 images, and `init_min_num_inliers=100` in
`sparse/0/project.ini` explains why. The custom pipeline has no such filter.

That looked like an obvious defect worth fixing. **It is not.** Running the
reconstruction with and without `Img16` gives the same 1041 3D points and camera
errors identical to two decimal places (0.97 vs 0.96 deg mean, 2.83 vs 2.77 max).
With 27 inliers the pair contributes nothing and breaks nothing.

Recorded because the reasoning was sound and the conclusion was still wrong — a
quality gate may become necessary with a denser pose graph (section 4), but on
the current evidence it is not a priority.

## 4. The star-shaped pose graph — hypothesis tested, largely refuted

This was the headline hypothesis of the whole teardown, and the measurement does
not support it.

### The claim

The original pipeline only consumed pairs involving the reference image
(`prueba.py:203` always calls `perform_pnp_and_triangulate(REFERENCE_IMAGE, new)`),
so nine verified cross-pairs were computed and discarded. Error grew with
distance from the reference (0.11 deg at distance 1.2, 2.77 deg at 3.8) and
adding cameras made the mean worse, which looked like unconstrained drift.

### What was actually measured

The same reconstruction code, the same thresholds, the same seed; the only
difference is which pairs it may use.

| | star (8 pairs) | complete (36 pairs) |
|---|---|---|
| tracks | 1185 | **2104** |
| observations | 4367 | **6928** |
| mean track length | **3.69** | 3.30 |
| cameras registered | 8 | **9** |
| 3D points | 915 | **1404** |
| mean rotation error | **0.754 deg** | 1.603 deg |
| max rotation error | **1.51 deg** | 7.20 deg |

Per camera, over the seven both reconstruct:

| | Img25 | Img13 | Img15 | Img24 | Img28 | Img14 | Img23 | **mean** |
|---|---|---|---|---|---|---|---|---|
| star | 0.249 | 0.206 | 0.395 | 0.569 | 1.143 | 1.206 | 1.510 | **0.754** |
| complete | 0.271 | 0.291 | 0.496 | 0.640 | 1.118 | 1.242 | 1.570 | **0.804** |

**The two agree to within 6% on every shared camera.** The complete graph's worse
headline number is entirely one camera: it additionally registers `Img12`, the
most distant and most weakly connected, at 7.20 deg.

### Why the hypothesis was wrong

Union-find chains transitively even on a star. Two non-reference cameras are
linked through a shared *reference keypoint* acting as a hub, so a star graph
still yields tracks spanning up to all nine views (mean length 3.69 here, in fact
*longer* than the complete graph's 3.30, since it keeps only well-connected
points). The pose graph was never as impoverished as "star" suggests.

What the complete graph genuinely buys is **reach, not accuracy**: 78% more
tracks, 59% more observations, 53% more 3D points, and one more camera. Points
the reference cannot see are unreachable without it — measured at 20% of
reconstructable points on synthetic data (`tests/test_tracks.py`).

### What this leaves

Adding cross-pairs is still worth doing: more scene coverage for the same
images, and the extra camera is a genuine registration rather than a failure.
The open problem it exposed is `Img12`, the most distant camera, registered on
few PnP inliers.

Threshold calibration turned out to help far more than any structural change
(section 1.6): tuning the three reconstruction thresholds by grid search took the
mean from 1.603 to 0.981 degrees and `Img12` from 7.20 to 2.84.

**A null result worth recording.** Re-running PnP for every camera after the
global refinement, against the improved 3D points, seemed obviously right:
cameras registered early were fixed against a fraction of the points that
eventually exist. Implemented, guarded so a pose is only replaced when it lowers
that camera's median reprojection error, it made things slightly *worse* --
0.981 to 1.001 degrees mean, `Img12` 2.835 to 3.004. Reprojection error on a
camera's own observations is a local criterion, and improving it does not imply
a better pose against an external reference. The code was reverted rather than
kept behind a flag.

Kept in full because the reasoning was sound, the evidence for it (error growing
with distance from the reference) was real, and the conclusion was still wrong.

## 5. Things that would *not* help — measured

These are the intuitive answers, and they are wrong here. Each was measured
rather than argued.

### GPU for the bundle adjustment

SVD of the 2524x1766 Jacobian, RTX 4090 vs CPU:

| | Time | vs numpy |
|---|---|---|
| CPU numpy, float64 | 1086 ms | 1.00x |
| **GPU torch, float64** | **1874 ms** | **0.58x — slower** |
| GPU torch, float32 | 130 ms | 8.38x |
| CPU->GPU transfer of 36 MB | 3.1 ms | negligible |

**The GPU loses in the precision the problem requires.** Two reasons compound:
the RTX 4090 is a consumer card whose fp64 is capped at 1/64 of fp32 (the 1874
vs 130 ms rows are the same card on the same matrix), and SVD is a sequential
multi-stage algorithm, not wide identical work.

Note the transfer is 3.1 ms, i.e. irrelevant — an earlier version of this
document blamed transfer overhead, which the measurement refutes. The obstacle is
the nature of the computation and the precision, not moving the data.

**Do not drop the BA to float32 to win that 8x.** Bundle adjustment solves
ill-conditioned systems where nearly-equal quantities are subtracted; fewer
digits destroys the information those differences carry.

The rule the two measurements jointly establish, and which decides every such
question in this codebase:

> Many identical independent operations -> GPU.
> Few large chained operations -> CPU.

RANSAC is the first (24x, section 2). Bundle adjustment is the second (0.58x).
Same library, same machine, opposite conclusions.

### Parallelising the finite-difference Jacobian

The 1766 evaluations are independent, so 24 cores would give ~24x. But the
Jacobian is 99.7 % structural zeros: parallelising wasted work across cores is
worse than not doing it. *Eliminate work before parallelising it.* Moot anyway —
the Jacobian evaluations were never the bottleneck (1.2).

### Hand-written CUDA kernels

Several rungs below Numba in effort-to-benefit, and unjustifiable at this size.

### Where the GPU is already correctly used

SuperPoint and LightGlue on 4032x2268 images — the genuinely data-parallel part
of the pipeline, and already on the GPU.

---

## 6. Library boundaries: what to implement, what to import

OpenCV provides every stage of this pipeline **except the one that is slow**:

| Stage | OpenCV |
|---|---|
| Fundamental / essential matrix | `findFundamentalMat`, `findEssentialMat` |
| Pose recovery | `recoverPose` |
| Triangulation | `triangulatePoints` |
| PnP + RANSAC | `solvePnP`, `solvePnPRansac`, `solvePnPRefineLM` |
| Homography (stage 4b) | `findHomography`, `warpPerspective` |
| **Bundle adjustment** | **absent** |

`cv2.detail.BundleAdjuster*` belongs to the panorama **stitching** module and
optimises rotation and focal length only — no translation, no 3D points. `cv2.sfm`
(contrib, wrapping Ceres) is not in the standard wheels.

The useful principle: **implement what the project exists to demonstrate, import
what is incidental.** Epipolar geometry, triangulation and BA are the deliverable
and should stay hand-written. Homography for change detection, I/O and utilities
should not.

Where OpenCV earns its place regardless:

- **As a reference oracle in tests.** Compare the custom `F` against
  `cv2.findFundamentalMat` on the same points. `ransac_filter.ipynb` already did
  this by Frobenius norm — it should have been a test, not a notebook cell.
- **`cv2.solvePnPRansac` + `cv2.setRNGSeed()`** to replace `ransac_dlt` (section 2).
- **`cv2.Rodrigues`** instead of `expm(crossMatrix(.))` with its object dtype.

### An environment hazard this exposed

Three different OpenBLAS builds load into a single process, with wildly different
performance on identical work:

```
numpy    numpy.libs/libopenblas64_p-...0.3.23     0.92 s
opencv   /lib64/libopenblas.so  (system)          3.30 s
scipy    scipy.libs/libopenblasp-...0.3.27       69.00 s
```

Same SVD, same process. This is the packaging mess behind section 1.0, and the
strongest argument for pinning the environment in a container: **performance needs
reproducibility too, not just results.**

---

## 7. Suggested order

Profile before optimising. Section 1.2 records getting this wrong three times in
a row. Every conclusion that survived did so because it was measured; several
plausible ones did not survive, and are kept as such.

| # | Change | Measured / expected | Effort | Status |
|---|---|---|---|---|
| 1 | Seeds + `UnboundLocalError` (2) | stage 3 is currently a dice roll | trivial | pending |
| 2 | Pin scipy/BLAS (1.0) | **38x**, no code change | environment | pending |
| 3 | `jac_sparsity` + `lsmr` (1.1) | **7.4x at 9 cameras** | one argument | **done** |
| 4 | Complete match graph (4) | +53% points, +1 camera; **no accuracy gain** | moderate | **done** |
| 5 | Guard weak registrations (4) | `Img12` at 2.8 deg; re-PnP tried, no gain | small | open |
| 6 | Batched RANSAC on GPU (2) | **24x**, across all pairs | moderate | pending |
| 7 | Analytic Jacobian (1.3) | cuts ~1800 lsmr iterations | large | pending |
| 8 | Sparse Schur (1.4) | only if #7 falls short | large | pending |

**#1 first**, because until stage 3 is deterministic none of its results can be
evaluated at all — four runs gave 12.1, 26.5, 31.1 and 5.5 degrees.

**#2 and #3 are alternatives on mutually exclusive code paths**, not a stack.
Both belong in the repository: #2 for small problems, #3 so it scales past ~6
cameras. #3 bought the ability to run 9 cameras at all.

**#4 is the one that matters for results.** #2 and #3 bought the experiment; #4
is what will make it worth running. Its input data is already computed and
currently discarded.

**Not on this list, deliberately:** GPU for the bundle adjustment (measured 0.58x,
section 5), float32 in the BA, hand-written CUDA, and replacing the core geometry
with OpenCV (section 6).

### Two things this document cannot fix

- **Stage 4b (change detection) does not exist.** Slides 31-32 describe it, but
  there is no `findHomography` or `warpPerspective` anywhere in the repository.
  It must be rewritten, not recovered.
- **Camera calibration is not reproducible.** The chessboard images were
  gitignored and are gone; only the resulting K matrices survive. This is a
  permanent limitation and should be documented as such rather than papered over.
