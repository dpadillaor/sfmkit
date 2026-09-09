# A guided tour of sfmkit

Every block below runs. Paste them into a Python session in order, each builds
on the last. Nothing here needs a photograph, a GPU, or a dataset: the tour
works on synthetic scenes whose answer is known by construction, so you can
always check what the library gives you against what it should give you.

```bash
conda activate mgrcv-sfm     # or: pip install -e ".[dev]"
python
```

---

## 1. The vocabulary: `Pose`

Everything in the library speaks in four types. Start with the one that appears
everywhere: a camera.

```python
import numpy as np
from sfmkit.core.types import Pose

p = Pose(np.eye(3), [0, 0, 5])
p.center                    # array([ 0.,  0., -5.])
p.transform(np.array([[0.0, 0.0, 10.0]]))    # array([[ 0.,  0., 15.]])
```

A `Pose` is **world-to-camera**: it maps a point in the world into the camera's
frame, `x_cam = R @ x_world + t`. That is COLMAP's convention and it never
varies in this package.

Note the sign: `t` is `[0, 0, 5]` but the camera *centre* is at `[0, 0, -5]`.
The translation is not where the camera is; the centre is `-Rᵀt`, which is what
`.center` gives you. Mixing these two up is the classic Structure-from-Motion
bug, which is why the distinction is a property rather than something you
compute by hand each time.

```python
p.compose(p.inverse()).t    # array([0., 0., 0.])
```

Read: [`core/types.py`](../src/sfmkit/core/types.py) — 165 lines, four
dataclasses. `Matches`, `Track` and `Reconstruction` will make sense as you meet
them below.

---

## 2. A laboratory: synthetic scenes

```python
from sfmkit.core.synthetic import make_scene

scene = make_scene(n_cameras=5, n_points=300, seed=0)
scene.images                      # ['cam00', 'cam01', ..., 'cam04']
scene.points.shape                # (300, 3)   the true 3D points
scene.keypoints["cam00"].shape    # (239, 2)   where they land in that image
```

Cameras on an arc looking at a wall of points, projected into each image. **You
know the right answer for everything**, which is what makes the rest of this
tour checkable rather than merely runnable — and it is why the test suite needs
no data.

Read: [`core/synthetic.py`](../src/sfmkit/core/synthetic.py) — 117 lines.

---

## 3. Two-view geometry

```python
from sfmkit.core.geometry import eight_point, sampson_distance

m = scene.matches_for("cam00", "cam02")
x0, x1 = m.points()
len(x0)                                  # 188 correspondences

F = eight_point(x0, x1)
np.linalg.matrix_rank(F, tol=1e-6)       # 2
sampson_distance(F, x0, x1).max()        # 2.8e-13
```

Two things worth noticing.

`F` has **rank 2**, not 3. A fundamental matrix maps points to lines, and all
those lines meet at the epipole — that degeneracy is a defining property, and
`eight_point` enforces it explicitly after the linear solve.

The Sampson distance is ~1e-13, i.e. exact to floating point. That is the check
you want on a fundamental matrix: every correspondence lies on the epipolar
line its partner induces. On real data it will be a pixel or two.

Read: [`core/geometry.py`](../src/sfmkit/core/geometry.py) — 237 lines.

---

## 4. From two views to 3D

```python
from sfmkit.core.geometry import (
    fundamental_to_essential, recover_pose, triangulate_two_view,
)
from sfmkit.core.metrics import rotation_error_deg

E = fundamental_to_essential(F, scene.K, scene.K)
rel = recover_pose(E, scene.K, x0, x1)

truth = scene.true_relative("cam02", "cam00")
rotation_error_deg(rel.R, truth.R)       # 0.0000 degrees
```

`F` knows nothing about the camera; `E` adds the calibration, and from `E` the
relative pose follows. Almost: `E` decomposes into **four** candidate poses, of
which only one puts the points in front of both cameras. `recover_pose` tries
all four and counts.

```python
X = triangulate_two_view(x0, x1, scene.K, scene.poses["cam00"],
                                 scene.K, scene.poses["cam02"])

ids = np.intersect1d(scene.visible["cam00"], scene.visible["cam02"])
np.abs(X - scene.points[ids]).max()      # 9.2e-14
```

The 3D points come back to machine precision. Translation is recovered only up
to scale, which is why the reconstruction later has to fix a gauge.

---

## 5. Tracks: the idea worth understanding

A track is one 3D point and every image that sees it. They are built by
union-find over the match graph, and the reason that matters is transitivity:

```python
from sfmkit.core.tracks import UnionFind, build_tracks, track_statistics

uf = UnionFind()
uf.union(("A", 0), ("B", 7))     # keypoint 0 of A matches keypoint 7 of B
uf.union(("B", 7), ("C", 3))     # which in turn matches keypoint 3 of C

uf.find(("A", 0)) == uf.find(("C", 3))    # True
```

**A and C were never matched, and they are now linked.** That is the whole
trick. Chains of pairwise matches become multi-view correspondences.

```python
pairs = [scene.matches_for(a, b)
         for i, a in enumerate(scene.images) for b in scene.images[i + 1:]]

stats = track_statistics(build_tracks(pairs))
stats["n_tracks"]           # 296
stats["mean_length"]        # 4.06
stats["length_histogram"]   # {2: 17, 3: 51, 4: 125, 5: 103}
```

Read the histogram: 103 points are seen by all five cameras. Those are the ones
that matter. A 2-view track gives 4 equations for 3 unknowns and is barely
determined; a 5-view track gives 10 for 3, is robust, and **rigidly couples all
five cameras**. Track length is what makes a reconstruction stiff.

Read: [`core/tracks.py`](../src/sfmkit/core/tracks.py) — 124 lines, the
shortest and most conceptually important module in the package.

---

## 6. Robustness: RANSAC

Real matches contain outliers. Corrupt 30% of them deliberately:

```python
from sfmkit.core.robust import ransac_fundamental

dirty = scene.matches_for("cam00", "cam02", noise=0.5, outlier_ratio=0.3, seed=1)
a, b = dirty.points()

r = ransac_fundamental(a, b, seed=42)
r.n_inliers, len(a)      # 136 of 188
r.n_iterations           # 95, not 1000
```

It recovered roughly the 70% that were not corrupted, and it stopped after 95
trials rather than burning all 1000: once the inlier ratio is known, the number
of trials still needed can be computed, so a clean pair is cheap.

```python
r2 = ransac_fundamental(a, b, seed=42)
np.array_equal(r.inliers, r2.inliers)    # True — same seed, same answer
```

**Every estimator takes a `seed` and no function draws on global random state.**
A result is a function of its inputs alone. Without that, running the same
pipeline twice gives two different answers and neither can be compared to
anything.

Read: [`core/robust.py`](../src/sfmkit/core/robust.py) — 244 lines, three
estimators with the same shape.

---

## 7. The whole thing

```python
from sfmkit.core.reconstruct import ReconstructionConfig, reconstruct

verified = []
for m in pairs:
    xa = m.keypoints0[m.pairs[:, 0]]
    xb = m.keypoints1[m.pairs[:, 1]]
    res = ransac_fundamental(xa, xb, threshold=3.0, seed=0)
    if res.converged:
        m.inliers = res.inliers
        verified.append(m)

out = reconstruct(verified, scene.K, build_tracks(verified),
                  ReconstructionConfig(seed=0))

rec = out.reconstruction
len(rec.poses), rec.n_points        # 5 cameras, 296 points
out.reports[-1].rmse_after          # 0.0000 px
```

And because the truth is known:

```python
from sfmkit.core.metrics import compare_poses

cmp = compare_poses(rec.poses, scene.poses, reference=rec.registered[0])
cmp["mean_rotation_error_deg"]      # 0.0000
```

Exact, on noiseless data. Add noise and outliers (as `tests/test_reconstruct.py`
does) and it degrades gracefully rather than falling over.

`out.reports` holds one row per step — which camera was added, how many points
existed, RMSE before and after each bundle adjustment. It is the same table the
CLI prints.

Read: [`core/reconstruct.py`](../src/sfmkit/core/reconstruct.py) — 378 lines,
mostly orchestration rather than new mathematics.

---

## Where to go next

**`core/bundle.py`** (199 lines) is the one deliberately left until last. It
packs poses and points into a single parameter vector, defines the residual, and
declares which residual depends on which parameter so SciPy can exploit the
sparsity. Read `BundleProblem.pack` and `unpack` first; they explain the gauge.

**`core/localize.py`** (132 lines) places a new image against a finished
reconstruction — the historical photograph, in the case study.

**The tests are executable documentation.** `tests/test_geometry.py` states the
properties that must hold; reading it is often faster than reading the
implementation:

```python
def test_rotation_is_valid(rng):
    R = rodrigues(rng.normal(size=3) * 2.0)
    assert np.allclose(R @ R.T, np.eye(3), atol=1e-12)
    assert np.isclose(np.linalg.det(R), 1.0)
```

**For the layout and the rules it enforces**, see
[architecture.md](architecture.md). **For the case study and the measurements
behind the design decisions**, see [optimizations.md](optimizations.md).
