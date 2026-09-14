# Tools

Ours, not the library's: the scripts that make the figures of the README and
the docs, and that ran the experiments behind a few of the defaults. They live
outside `packages/` on purpose — they are not installed, not imported by
anything, and not copied into the image. Run them from the repo root, in the
`sfmkit` environment.

| Script | What it does |
|---|---|
| `changes_animation.py` | The old photograph landing on today's and what changed: `website/docs/figures/old_photo.{webp,mp4}` |
| `then_and_now.py` | The pair side by side, `website/docs/figures/then_and_now.jpg` |
| `sweep.py` | The grid search over the reconstruction's thresholds, scored against COLMAP |
| `report.py` | A run's numbers gathered into one table |
| `experiment_topology.py` | How the matching graph changes with the pairs kept |

`changes_animation.py` sets its text in the viewer's own IBM Plex Sans, which
it reads from `packages/viewer/.../vendor/fonts` as woff2; that needs `brotli`
alongside the fontTools matplotlib already brings. Without it the text falls
back to DejaVu Sans and everything else is the same.
