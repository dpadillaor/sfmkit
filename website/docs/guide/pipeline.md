# The pipeline

Ten stages, each a command. `sfmkit run` does them in order; any one of them
can be run on its own, because each reads what the one before it wrote.

![The sfmkit pipeline](../figures/pipeline.svg)

```bash
sfmkit run --config projects/valencia/configs/cpu.yaml      # writes projects/valencia/runs/cpu/
```

<video controls muted loop playsinline width="100%" poster="../../figures/then_and_now.jpg">
  <source src="../../figures/growth.mp4" type="video/mp4">
</video>

*The model being built: every frame is a real step of `reconstruct`, from the
seed pair to the global refinement.*

## What each stage does

| Stage | What it does | What it leaves |
|---|---|---|
| `calibrate` | The camera's focal length and image centre, without which nothing can be measured | `K.txt` |
| `match` | Distinctive points in each photograph, paired between photographs | a file per pair |
| `verify` | Throws away pairings that do not fit the geometry of two views | the same pairs, inliers only |
| `reconstruct` | Builds the 3D model: two photographs to start, then one at a time | the reconstruction |
| `localize` | Places the old photograph in that model | its pose and camera |
| `colmap` | The COLMAP model to be scored against | COLMAP's text model |
| `dense` | Optional, needs CUDA: a dense cloud from COLMAP's model | `fused.ply` |
| `evaluate` | How far every camera is from COLMAP's | `evaluation.json` |
| `changes` | Overlays the old photograph on a modern one and marks what differs | the overlay and the mask |
| `figures` | The plots for a finished run | `figures/` |

Details of the options each one takes are in the [CLI reference](cli.md); the
YAML that drives them, in [Configuration](config.md).

## How the reconstruction is built

`reconstruct` is the heart of it, and it works the way incremental SfM has
worked since Bundler.

![What reconstruct does, step by step](../figures/reconstruct.svg)

*The loop is drawn as a loop: the seed pair happens once, the five steps beside
it once per photograph. Every step names the idea it rests on rather than the
function that carries it.*

1. **An initial pair**, chosen for the pair that has both enough inliers and a
   wide enough angle between the two cameras — a pair that is easy to match is
   often too shallow to triangulate.
2. **Triangulate** what those two see, dropping points whose rays meet at too
   narrow an angle to be trusted.
3. **Register the next camera** by PnP against the points already in the map,
   keeping the RANSAC inliers.
4. **Triangulate what it adds**, filter observations that reproject too far,
   and **bundle adjust**: every camera and every point, minimising the
   reprojection error under a Huber loss.
5. Repeat until no photograph can be registered, then **refine globally** once
   more.

The bundle adjustment is our own: Levenberg–Marquardt with an analytic
Jacobian, the Schur complement to eliminate the points, gauge fixed on the
first camera and the baseline of the second, and the robust loss applied as
iteratively reweighted least squares. It is about 58 times faster than the
`scipy.optimize.least_squares` version it replaced, which never converged on
these problems; that one is still there, as `sfm.bundle_solver: scipy`, because
a claim like this ought to be re-runnable.

## The old photograph is handled apart

It was taken by another camera, of unknown focal length, perhaps cropped, a
century before the rest. So it is matched against the reference only, left out
of the reconstruction, placed against the finished model by `localize`, and
scored on its own. [Results](../project/results.md) has what that cost and what
it bought.
