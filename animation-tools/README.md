# Animation tools

The scripts that draw the pictures. They live outside `packages/` on purpose:
not installed, not imported by anything, not copied into an image. Run them
from the repository root, in the `sfmkit` environment.

They need a finished run to draw from (`projects/valencia/runs/gpu-dense` for
the ones that want a dense cloud), so they are not something a stranger can
execute on a fresh clone. They are here so that a figure is never a picture
nobody knows how to remake.

| Script | What it does |
|---|---|
| `changes_animation.py` | The old photograph landing on today's and what changed: `website/docs/figures/old_photo.{webp,mp4}` |
| `then_and_now.py` | The pair side by side, `website/docs/figures/then_and_now.jpg` |
| `growth_animation.py` | Two films from one run: the model growing camera by camera (`--view map`), and the comparison against COLMAP built up step by step (`--view colmap`) |
| `animate.py` | Not run on its own: writing a list of frames out as WebP, GIF or MP4, shared by the two above |

`changes_animation.py` sets its text in the viewer's own IBM Plex Sans, which
it reads from `packages/viewer/.../vendor/fonts` as woff2; that needs `brotli`
alongside the fontTools matplotlib already brings. Without it the text falls
back to DejaVu Sans and everything else is the same.


## The figures themselves

They live in `website/docs/figures/`, one copy, because MkDocs only reads
inside its own documentation directory while the README can reach anywhere in
the repository. The README's links are relative and GitHub resolves them; the
site's are relative to its own pages.

| File | What it shows | How it is made | Used in |
|---|---|---|---|
| `then_and_now.jpg` | The whole input: the undated photograph, the one it is matched against, and the rest of the set underneath | `python animation-tools/then_and_now.py`, from the repo root. Reads the images out of the config, and turns them as their EXIF says | README, the site |
| `old_photo.webp`, `old_photo.mp4` | The old photograph landing on today's, what changed, and what changed where | `python animation-tools/changes_animation.py --layout side --format webp --width 860 --quality 38` (the MP4: `--format mp4 --width 1400`) | README, the site |
| `growth.webp`, `growth.mp4` | The map being built, camera by camera | `python animation-tools/growth_animation.py --format webp --width 1000 --out website/docs/figures/growth` (the MP4: `--format mp4`) | README, the site |
| `viewer.png` | The viewer on the frozen GPU run, so its counts are the ones the README quotes | `sfmview --projects projects --port 8124`, then `google-chrome --headless=new --disable-gpu --use-angle=swiftshader --window-size=1400,900 --virtual-time-budget=30000 --screenshot=viewer.png "http://localhost:8124/#valencia/reference-gpu-dense"` | README, the site |
| `pipeline.svg` | The ten stages on three lanes, and what flows between them | Written by hand; see below | README, the site |
| `containers.svg` | The three containers, the disk they share and the one port that leaves | Written by hand, the same way | README, the site |
| `reconstruct.svg` | What `reconstruct` does, step by step | Written by hand, the same way | the site |
| `localize.svg` | What `localize` does, step by step | Written by hand, the same way | the site |
| `cameras.png`, `comparison.png`, `tracks.png` | A finished run's two models, and its tracks | Copied from a run's `figures/` (`sfmkit figures`) | the site |
| `matches.jpg`, `epipolar.jpg`, `residuals.jpg` | Diagnostics of the stages that got there | The same, resized to 1400 px wide (the PNGs were 1-2 MB each) | the site |
| `changes.jpg` | What differs between the old photo and a modern one | Copied from a run's `changes/` (`sfmkit changes`), resized to 1600 px | the site |

## The typefaces

Every figure here is lettered in the two faces the viewer is set in, IBM Plex
Sans and Roboto Mono, kept once in `packages/viewer/src/sfmview/web/vendor/fonts`.
They are woff2, which neither PIL nor matplotlib reads, so `animate.py`
decompresses one through fontTools when it is asked for: `typeface()` hands the
bytes to the tools that letter with PIL, and `use_project_fonts()` registers
both with matplotlib for the ones that draw with it. Without fontTools
installed, both fall back to matplotlib's DejaVu and the figure still renders.

The figures `sfmkit figures` writes are not lettered this way, and cannot be:
they are drawn inside `packages/sfmkit`, which does not get to reach into the
viewer's files for a font.

## `pipeline.svg`

A hand-written SVG rather than a mermaid block: GitHub picks mermaid's fonts,
colours and layout, and the result always looks generated. The SVG is still
text, so it is edited and diffed like code. To preview it, make the viewer's
typefaces visible to fontconfig once, then render with cairosvg:

```bash
python - <<'FONTS'
import sys; sys.path.insert(0, "animation-tools")
from pathlib import Path
from animate import _truetype, PLEX, MONO
for src, name in ((PLEX, "IBMPlexSans-Regular.ttf"), (MONO, "RobotoMono-Regular.ttf")):
    Path.home().joinpath(".local/share/fonts", name).write_bytes(_truetype(src))
FONTS
fc-cache -f ~/.local/share/fonts
python -c "import cairosvg; cairosvg.svg2png(
    url='website/docs/figures/pipeline.svg', write_to='/tmp/pipeline.png', scale=2)"
```

### Layout

Canvas `1090 x 512`, on its own white card (`rx=14`) so it reads the same
against GitHub's two themes and against the site, which is dark only.

Three lanes, because two of the ten stages run beside the reconstruction rather
than after it. The spine is the middle one; the old photograph hangs above it,
COLMAP runs below on nothing but the photographs, and the two things a reader
leaves with sit at the end.

```
x:  24 -- 216   260 --------------------------- 855   895 -- 1065
    inputs      THE OLD PHOTOGRAPH   y  24-134         RESULTS
                BUILD THE MODEL      y 160-350         y 250-446
                COLMAP, ON ITS OWN   y 372-482
```

* **Lane**: `fill #f7f7f5`, `stroke #e7e7e3`, `rx=5`. Its label sits at the
  bottom left, so an arrow can enter a card from above without crossing it. The
  two lanes at the edges take nothing from above and label themselves at the top.
* **Card**: `145 x 64`, `rx=4`, white, with a 3 px bar down its left edge in the
  data's colour, which is how the viewer marks a selected run. Stage name at
  `(x+16, y+26)`, description lines at `y+45` and `y+59`.
* **Arrows**: right angles only. Each takes the colour of whatever sends it, so
  the three that meet at `evaluate` say which model each one carries without a
  word. The cables to the results climb the gutter at `x=865` and `x=879`.

### Style

Both typefaces and the three data colours are the viewer's own, so a figure and
the page it belongs beside are set the same way. Plex and Roboto Mono fall back
to the system's sans and mono for a reader who has neither installed.

| Element | Font | Colour |
|---|---|---|
| Stage name | Roboto Mono, 14.5px | the lane's, darkened for white |
| Description | IBM Plex Sans, 11.5px | `#6d6d68` |
| Lane label | IBM Plex Sans, 10px, tracked | `#9a9a94` |
| Flow label | Roboto Mono, 9px | `#8e8e88` |

| Lane | Accent bar | Stage name | Cable |
|---|---|---|---|
| Build the model | `#f2a93b` | `#96620c` | `#d9911f` |
| The old photograph | `#ff6fae` | `#b23a6c` | `#e8629b` |
| COLMAP | `#56a8f5` | `#1a6bb5` | `#3f92e0` |
| Results | `#3b3b38`, `#b9b9b3` | `#1b1b1a`, `#6d6d68` | |

### Changing it

* Keep a description to two lines of about 20 characters. Past that it runs
  over the card, and the card is sized so three of them and their gaps fill a
  lane.
* Say what a stage does and then how, in that order. Read down the diagram and
  `match` and `colmap` fall into the same shape, which is what makes the two
  matchers comparable at a glance.
* A new stage is a card in its lane plus the arrows into and out of it. If a
  lane grows, widen every lane and move the results frame and the gutter with
  them; the three lanes share a left and a right edge.
* Check it in a browser, zoomed and at the width the site gives it, before
  committing.

### What it leaves out

Every arrow is a directory the next stage reads, but not every read is drawn.
`localize` also opens `verify/`, which is how the old photograph reaches a model
it was kept out of, and `evaluate` also opens `calibrate/`, to set our K beside
COLMAP's. Both belong in the prose about those stages rather than in a diagram
of ten boxes.


## `containers.svg`

The same hand-written SVG as `pipeline.svg`, and the same tokens, drawn from
`compose.yaml` and the two Dockerfiles. Canvas `1040 x 612`.

It is the one figure that does not use the data colours for meaning, because
its subject is not the data. Instead it borrows a vocabulary diagrams of
infrastructure already have:

* **A window with a title bar** for the terminal and the browser, each showing
  what it would really show: the command in one, `127.0.0.1:8000` in the
  address bar of the other, and a scatter of amber and blue points for the page
  it renders.
* **Three stacked bars** in a card's corner for a container, in that
  container's colour. They are the image's layers, and they are the only glyph
  here that says anything about Docker.
* **A cylinder** for a named volume, **a folder** for a directory on your disk.
  The difference matters: the cylinders sit inside the boundary and the folder
  outside it, which is what a bind mount is.
* **A dashed boundary** in Docker's blue, `#2496ed`, with its label sitting on
  the line over a white gap, the way a fieldset legend does.

No whale and no logo. Docker's mark is a trademark, redrawing it would be a
knock-off, and an external asset would stop this file being text that diffs.
The stacked cargo is the metaphor without the brand.

Ports are pills beside the service name, and their colour is the argument:
`:6379` is grey and never leaves, `:8000` is the boundary's own blue because it
is the only one that crosses it. `cli` has none, which says it listens nowhere.

### What it leaves out

`cli-gpu`, which is `cli` with another image and `gpus: all`; the healthcheck
that `viewer` waits on, which its card describes in words; and that the images
are published to two registries so `docker compose pull` fetches rather than
builds. All three are on the page the figure sits on.


## `reconstruct.svg`

The level `pipeline.svg` cannot reach: one box of it, opened. Canvas `1020 x 700`,
the same tokens, the same cards.

Its shape carries an argument the pipeline diagram's lanes would get wrong. There,
lanes run in parallel. Here they do not: the seed pair happens once and then the
loop runs, so the two columns are joined by a line that merges with the loop's own
return, and only the loop feeds the last step. Three phases, numbered, because
they are in sequence; the numbers on `pipeline.svg` were dropped for the opposite
reason.

Two rules the text follows, and they are worth keeping:

* **Nothing in it is Valencia's.** No camera counts, no pixel errors, no "twelve
  times". The loop is labelled by its stopping condition, and the last step by
  the reason it exists. Those hold for any set of photographs; the numbers live
  in Results.
* **The second line describes what happens, and a function name only rides
  behind it if it fits.** A card whose second line was just `ransac_pnp` taught
  nothing. Descriptions take a capital letter; identifiers never do, because an
  identifier is not a sentence.

Widths, measured: a title fits about 50 characters at 12.5px, a description
about 61 at 10px in the mono face. Past that it runs over the card.


## `localize.svg`

The same again for the other stage the pipeline diagram cannot open. Canvas
`1000 x 570`, one column, five steps.

It was drawn as a fork first, and that was wrong. `localize_image` takes a `K`
and solves a PnP when it is given one, so the figure showed a choice; but
`cmd_localize` never passes one, so the stage always takes the other road and
solves the whole projection matrix. A diagram that shows a branch the program
never takes is worse than one that shows nothing, and the label on the unused
side made it worse still: the modern cameras are not localised here at all,
they are registered in `reconstruct`.

The contrast is worth keeping, so it survives as a grey aside beside step two,
outside the flow on a dashed leader. It reads as an aside because it is one.
