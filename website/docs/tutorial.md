# Tutorial

One pass from nothing to a reconstruction you can turn around in a browser,
with the photographs that come with the repository. Then the same on
photographs of your own.

Half an hour on a CPU, a few minutes on a GPU. You need Python 3.11, git, and
an internet connection the first time, for the feature weights.

## 1. Get it

```bash
git clone https://github.com/dpadillaor/sfmkit
cd sfmkit
conda create -n sfmkit python=3.11 -y
conda activate sfmkit
pip install --no-deps -r packages/sfmkit/requirements-cpu.txt
pip install --no-deps -e packages/contracts -e packages/sfmkit
```

Check it answers:

```bash
sfmkit run --help
```

The photographs are already there: fourteen of the Plaza de la Virgen in
Valencia, taken with a phone, and `Img_Old`, an undated one of the same square
from perhaps a century earlier.

## 2. Run the pipeline

```bash
sfmkit run --config projects/valencia/configs/no-colmap.yaml
```

That config scores the result against a COLMAP model saved in the repository,
so nothing needs COLMAP installed. Use `projects/valencia/configs/cpu.yaml` instead if
you have it and would rather COLMAP reconstructed the scene itself.

What you will see, in order:

**`calibrate`** reads the focal length out of the photographs' EXIF, and prints
the K it derived. **`match`** downloads the SuperPoint and LightGlue weights
(53 MB, once) and pairs up the photographs — this is the slow part on a CPU.
**`verify`** throws away the pairings that do not fit two-view geometry.
**`reconstruct`** picks a starting pair and adds a camera at a time, printing a
row per step: how many cameras are in, how many points, and the reprojection
error before and after each bundle adjustment. **`localize`** places the old
photograph against the finished model. **`colmap`** brings in the reference
model, **`evaluate`** scores ours against it, **`changes`** overlays the old
photograph on a modern one, and **`figures`** draws the plots.

At the end you should see fourteen cameras, about 2 850 points, and a mean
rotation error against COLMAP of around a third of a degree.

## 3. Look at it

```bash
conda create -n sfmview python=3.11 -y
conda activate sfmview
pip install --no-deps -r packages/viewer/requirements.txt
pip install --no-deps -e packages/contracts -e packages/viewer
sfmview --projects projects --data data
```

Open <http://127.0.0.1:8000> and pick the run. You are looking at two
reconstructions in one frame: ours in amber, COLMAP's in blue, aligned the way
`evaluate` aligns them. Hover a camera to see which photograph it is, click it
to look through it. The old photograph is the one in its own colour, set among
the modern ones.

The pictures the run drew for itself are in `projects/valencia/runs/no-colmap/figures/`
and `…/changes/`; the overlay of the old photograph on today's is the one worth
opening first.

## 4. Watch one being built

`reconstruct` publishes each step as it finishes, and the viewer draws them
live, with a timeline to rewind. It needs a Redis between them. With Docker
that is one command:

```bash
docker compose up -d viewer        # Redis, then the viewer
docker compose run --rm cli reconstruct --config projects/valencia/configs/cpu.yaml
```

Without Docker, run a Redis of your own and point both at it:

```bash
sfmview --projects projects --broker redis://localhost:6379
SFMKIT_BROKER=redis://localhost:6379 sfmkit reconstruct --config projects/valencia/configs/cpu.yaml
```

## 5. Your own photographs

`sfmkit new` lays the project out and copies the photographs into it:

```bash
sfmkit new plaza --photos ~/Pictures/plaza
```

```
projects/plaza/
├── data/scene/     the photographs, copied in
├── configs/        cpu.yaml, written for you, listing them
└── runs/           written when you run
```

Nothing in the config names the project: the file's own location says which one
it belongs to. Then:

```bash
sfmkit run --config projects/plaza/configs/cpu.yaml
```

A first project usually has no historical photograph to place and no COLMAP
installed to be scored against, and the config it was given says nothing about
either. `run` walks past a stage the config does not ask for, so what happens
is `calibrate`, `match`, `verify`, `reconstruct` and the figures. Uncomment the
two sections when you want the rest:

```yaml
localize:
  query: Img_Old           # the odd photograph out, kept out of the reconstruction

colmap:
  matches: colmap          # needs COLMAP installed
```

Without `--photos` you get the same layout empty, and the config tells you what
to put where. Every key it leaves out is in [the configuration
reference](guide/config.md).

What matters for the photographs themselves:

**Move between shots, do not turn on the spot.** Structure from Motion recovers
depth from parallax; a panorama taken from one point has none, and nothing will
triangulate.

**Overlap generously.** Every photograph should share a good half of its view
with at least one other.

**One camera, one setting.** If the EXIF says a different focal length in
different photographs — digital zoom does this — `calibrate` will be wrong for
some of them.

**Eight to twenty photographs** is a comfortable range to start. Fewer and the
model is thin; many more and matching every pair starts to cost.

For the old photograph, if you have one: it does not need to share a camera or
a century with the rest, but it does need to be recognisably the same place
from a not too different angle. It is matched against the reference only, kept
out of the reconstruction, and placed afterwards —
[why](project/results.md#the-115-argument) is the most interesting part of the
project.

## Where to go next

The [pipeline](guide/pipeline.md) explains what each stage does and how the
reconstruction is built; the [configuration](guide/config.md) lists every key
you can turn; [what a run holds](guide/runs.md) says what all those files are.
If something did not work, the [FAQ](faq.md) is shorter than this page.
