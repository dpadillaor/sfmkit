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
pip install --no-deps -e packages/sfmkit
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
sfmkit run --config configs/valencia/no-colmap.yaml
```

That config scores the result against a COLMAP model saved in the repository,
so nothing needs COLMAP installed. Use `configs/valencia/cpu.yaml` instead if
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
pip install --no-deps -e packages/viewer
sfmview --runs runs --data data
```

Open <http://127.0.0.1:8000> and pick the run. You are looking at two
reconstructions in one frame: ours in amber, COLMAP's in blue, aligned the way
`evaluate` aligns them. Hover a camera to see which photograph it is, click it
to look through it. The old photograph is the one in its own colour, set among
the modern ones.

The pictures the run drew for itself are in `runs/valencia/no-colmap/figures/`
and `…/changes/`; the overlay of the old photograph on today's is the one worth
opening first.

## 4. Watch one being built

`reconstruct` publishes each step as it finishes, and the viewer draws them
live, with a timeline to rewind. It needs a Redis between them. With Docker
that is one command:

```bash
docker compose up -d viewer        # Redis, then the viewer
docker compose run --rm cli reconstruct --config configs/valencia/cpu.yaml
```

Without Docker, run a Redis of your own and point both at it:

```bash
sfmview --runs runs --broker redis://localhost:6379
SFMKIT_BROKER=redis://localhost:6379 sfmkit reconstruct --config configs/valencia/cpu.yaml
```

## 5. Your own photographs

Say your project is called `plaza`. Put the photographs in
`data/plaza/scene/`, named however you like — `Img01.jpg`, `Img02.jpg`, … is
what the examples do — and write `configs/plaza/first.yaml`:

```yaml
dataset: plaza
name: first
seed: 0

calibrate:
  exif: true               # the focal length out of the photographs themselves

sfm:
  images: [Img01, Img02, Img03, Img04, Img05]   # without the extension
  reference: Img01         # the camera everything is expressed against
  exhaustive: true
  device: auto             # cuda if there is a GPU

localize:
  query: Img_Old           # the odd photograph out; omit the section if there is none

colmap:
  matches: colmap          # needs COLMAP installed
```

```bash
sfmkit run --config configs/plaza/first.yaml
```

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
