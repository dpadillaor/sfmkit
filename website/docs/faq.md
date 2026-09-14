# Questions

## Do I need COLMAP installed?

No. COLMAP is what the result is *scored against*, not what produces it. The
repository carries a saved COLMAP model of the same photographs, and
`projects/valencia/configs/no-colmap.yaml` uses it:

```bash
sfmkit run --config projects/valencia/configs/no-colmap.yaml
```

You need it for two things only: to have COLMAP reconstruct your own scene as
an independent reference, and for the `dense` stage, which is COLMAP's stereo.

## Do I need a GPU?

No. Only `match` uses one, where it is about ten times faster; everything after
it is numpy and runs the same either way. The whole Valencia example runs on a
CPU in around half an hour.

The one thing a GPU is required for is `dense`, COLMAP's dense point cloud:
that is CUDA-only in COLMAP itself, and the pipeline refuses the stage rather
than pretending.

A CPU run and a GPU run of the same config give slightly different results,
because matching differs. Both are checked; the difference is in the third
decimal of the error.

## Where do the feature weights come from, and why are they not included?

`match` uses SuperPoint and LightGlue, whose weights (53 MB) are downloaded on
first use into PyTorch's cache. They are not in this repository and not in its
images: SuperPoint's weights are Magic Leap's, released for non-commercial
research, and not ours to pass on. Whoever downloads them takes those terms on
themselves.

Offline, the run stops with the two URLs and the directory to put the files in,
rather than a stack trace. In Docker they live in a volume mounted at
`/opt/torch`, so the download happens once; `SFMKIT_WEIGHTS` points that at a
directory of your own.

## Why is the old photograph handled apart?

Because it is a different camera, of unknown focal length, possibly cropped, a
century older. Concretely, it is matched against the reference photograph only
(it shares too few features with the rest), left out of the reconstruction so
that a poorly constrained camera cannot bend the map, placed against the
finished model by `localize`, and scored on its own.

And its intrinsics are estimated rather than assumed: `localize` solves for a
whole projection matrix by RANSAC and decomposes it, because assuming the
phone's calibration for a photograph that size misplaces the camera badly.

[The 11.5° argument](project/results.md#the-115-argument) is what came of
taking that seriously.

## My photographs do not reconstruct. What now?

In order of how often it is the answer:

**You turned instead of moving.** Photographs taken from one spot, panning,
have no parallax and cannot be triangulated. Walk between shots.

**Not enough overlap.** Each photograph should share a good half of its view
with another.

**Digital zoom.** A phone reports the lens's focal length, not the crop's, so a
zoomed photograph is calibrated wrong — 17% out on the one in this project that
had it. Keep to one setting, or drop the odd ones.

**A flat, textureless or repetitive scene.** Features need something to hold
on to, and a repeating facade matches itself.

To see what happened rather than guess: `verify` prints how many pairs survived,
`reconstruct` prints a row per camera it registers, and `sfmkit figures` draws
the matches and epipolar lines for a pair.

## Can I use it on something other than Valencia?

Yes — that is what `projects/<name>/data/scene/` and `projects/<name>/configs/*.yaml` are
for. The [tutorial](tutorial.md#5-your-own-photographs) has the shape of a
config for your own photographs.

## Why write a bundle adjustment instead of using Ceres or scipy?

scipy's was the first implementation, and it is still there
(`sfm.bundle_solver: scipy`). It turned out never to converge on these
problems: it exhausted its evaluation budget on every bundle. The one in
`core/bundle_schur.py` — Levenberg–Marquardt, an analytic Jacobian, the points
eliminated with the Schur complement — is about 58 times faster *and* reaches a
lower cost. [The numbers](project/results.md#the-bundle-adjustment).

## Does the viewer need the library installed?

No, and it must not be: the viewer is a separate package that reads runs off
disk through [a fixed set of files](viewer/index.md#what-the-viewer-reads) and,
for live progress, [a message format](viewer/live.md). CI proves the point by
failing if `import sfmkit` succeeds in the viewer's environment.

## Is any of this uploaded anywhere when I run it?

No. Everything runs locally and writes to `runs/`. The only thing that leaves
your machine is the one-time download of the feature weights, and only if they
are not already cached.
