# Figures

| File | What it shows | How it is made | Used in |
|---|---|---|---|
| `then_and_now.jpg` | The historical photo beside a modern one | `python tools/then_and_now.py`, from the repo root | README |
| `old_photo.webp`, `old_photo.mp4` | The old photograph landing on today's, what changed, and what changed where | `python tools/changes_animation.py --layout side --format webp --width 1000 --quality 55` (the MP4: `--format mp4 --width 1400`) | README, the site |
| `pipeline.svg` | The stages, grouped in three blocks | Written by hand; see below | README |
| `cameras.png`, `comparison.png`, `matches.png`, `epipolar.png`, `residuals.png`, `tracks.png` | Diagnostics of a finished run | Copied from a run's `figures/` (`sfmkit figures`) | README.old.md |
| `changes.png` | What differs between the old photo and a modern one | Copied from a run's `changes/` (`sfmkit changes`) | README.old.md |

## `pipeline.svg`

A hand-written SVG rather than a mermaid block: GitHub picks mermaid's fonts,
colours and layout, and the result always looks generated. The SVG is still
text, so it is edited and diffed like code.

### Layout

Canvas `920 × 426`, with its own white background (`rx=16`) so it looks the
same in GitHub's light and dark themes.

```
x: 20 ────── 166   190 ──────────────────────────────── 900
   inputs          1 · Build the 3D model      y 24–244
                   2 · Use the old photo       3 · Check the result
                   x 190–535, y 276–404        x 555–900, y 276–404
```

* **Inputs**: pills `146 × 40`, `rx=20`, under a `YOU PROVIDE` label.
* **Block**: panel `fill #f8fafc`, `stroke #e2e8f0`, `rx=12`. Its title sits at
  the bottom left, after a numbered badge (circle `r=11`), so arrows can enter
  the cards from above without crossing it.
* **Card**: `150 × 62` in block 1, `140 × 62` in blocks 2 and 3, `rx=8`, white.
  Stage name at `(x+14, y+24)`, description lines at `y+42` and `y+56`.
* **Arrows**: right angles only, never crossing, `stroke #64748b`, width 1.6,
  one shared arrowhead marker. The paths between blocks run in the gap between
  `y=244` and `y=276`, at different heights so they do not overlap.

### Style

| Element | Font | Colour |
|---|---|---|
| Stage name | monospace, 14px, 600 | block colour, dark |
| Description | sans, 12px | `#475569` |
| Block title | sans, 14px, 600 | `#0f172a` |

| Block | Badge | Card border | Stage name |
|---|---|---|---|
| 1 · Build the 3D model | `#2563eb` | `#93c5fd` | `#1d4ed8` |
| 2 · Use the old photo | `#b45309` | `#f2c46d` | `#92400e` |
| 3 · Check the result | `#047857` | `#6ee7b7` | `#047857` |

Old photo pill: `#f3ead8` / `#b08d57` (sepia). Modern photos: `#eef2f7` / `#94a3b8`.

### Changing it

* Keep descriptions to two lines of about 16 characters: that is what fits.
* A new stage is a card in its block plus the arrows into and out of it; if
  a block grows, widen or heighten its panel and move the panels after it.
* Check it in a browser, zoomed and at the width GitHub gives it (about
  830 px), before committing. `figures` is left out on purpose: it draws plots,
  it is not a step of the method.
