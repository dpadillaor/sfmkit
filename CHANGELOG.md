# Changelog

What changed between versions, kept by hand in the style of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). A version is a tag,
and a tag is what publishes the images, so the two never drift apart.

## Unreleased

The first release, `v0.1.0`, is what this section becomes when it is tagged.
What it will carry:

### Added

- **`sfmkit`**, a Structure-from-Motion library in four layers
  (`apps → render → data → core`), enforced by import-linter rather than by
  good intentions. Ten stages, each a command, `sfmkit run` doing them in
  order: `calibrate`, `match`, `verify`, `reconstruct`, `localize`, `colmap`,
  `dense`, `evaluate`, `changes`, `figures`.
- **A bundle adjustment of its own** — Levenberg–Marquardt, an analytic
  Jacobian, the points eliminated with the Schur complement — 58× faster than
  the `scipy.optimize.least_squares` it replaced, and to a lower cost.
- **An old photograph placed in the model**, its whole projection matrix
  solved for, focal length included, then refined in pixels under a Huber loss:
  14 px of reprojection down to 2, and the same answer on every seed.
- **A change map** between that photograph and a modern one, once the two are
  aligned and their tones matched.
- **Every result scored against COLMAP** run from scratch on the same
  photographs: 0.30° mean rotation error over 14 cameras on Valencia, 0.60° on
  the old photograph.
- **`sfmview`**, a web viewer of runs in ports and adapters: both models and
  the dense cloud in one frame, a photograph inside its camera's frustum, and
  a run drawn **as it is being built**, with a timeline to rewind it. It never
  imports sfmkit; a test fails if its environment so much as can.
- **The messages between them written down** — `contracts/step.schema.json`,
  an AsyncAPI document for the channels, OpenAPI from the viewer itself — and
  checked by both test suites.
- **Images for both packages**, CPU and CUDA, and a compose file that runs the
  pipeline, the viewer and a broker together.
- **A documentation site**, a tutorial, and the measurements behind every
  number quoted, arguments included.
