# The viewer

`sfmview` is a web viewer for sfmkit runs: both reconstructions in 3D, the old
photograph as each of them placed it, COLMAP's dense cloud, and — while
`reconstruct` works — the model growing step by step, with a timeline to rewind
it.

It is its own package, with its own dependencies and its own image, and it does
not import sfmkit. The two share a set of files and a message format, and
nothing else.

![The viewer on Valencia, with the dense cloud](../figures/viewer.png)

Its look is a dense tool panel in the manner of Blender and Rerun: neutral
greys, square corners, hairlines, figures in monospace. One signal colour,
international orange, marks what is selected, current or live; the data keep
their own — amber for sfmkit, blue for COLMAP.

## Running it

```bash
conda activate sfmview
sfmview --runs runs --data data      # http://127.0.0.1:8000
```

| Option | Default | | Environment |
|---|---|---|---|
| `--runs` | `runs` | sfmkit's runs directory | `SFMVIEW_RUNS` |
| `--data` | `data` | the datasets, for the photographs | `SFMVIEW_DATA` |
| `--host` | `127.0.0.1` | address to listen on; `0.0.0.0` in a container | `SFMVIEW_HOST` |
| `--port` | `8000` | | `SFMVIEW_PORT` |
| `--broker` | — | Redis URL for live progress | `SFMVIEW_BROKER` |

With Docker: [Install with Docker](../install/docker.md#the-viewer).

## What it shows

- **Runs**, with their stages, their metrics, where each stage ran (CPU or GPU),
  and whether one is live right now.
- **Both models in one frame**: sfmkit's and COLMAP's, aligned the way
  `evaluate` aligns them, so what is drawn is what is scored.
- **The old photograph**, in its own colour, as sfmkit placed it and as COLMAP
  did — the disagreement between the two is visible rather than a number in a
  table.
- **The photographs themselves**: hover a camera to see which one it is, click
  it to look through it, with its frustum drawn to the scene and its reach and
  transparency under your hand.
- **The dense cloud**, when the run has one.

![A run followed live](../figures/viewer_live.png)

## Live progress

Pointed at the same Redis that sfmkit publishes to, the viewer follows a run as
it is built: each camera appears as it is registered, and the timeline can be
dragged back through the steps. A run at work is marked live in the list; one
whose heartbeat stops before its `end` — sfmkit killed, or the broker lost — is
no longer shown as live.

The messages are documented in [Live messages](live.md).

## What the viewer reads

The contract with sfmkit, and the whole of it. A run is
`runs/<project>/<config>/`, one directory per stage; the viewer only reads, and
only these:

| File | Stage | What it takes |
|---|---|---|
| `*/manifest.json` | every stage | `stage`, `timestamp`, `config` (`sfm.reference`, `localize.query`), `device` where a stage records one; from `evaluate`'s, the metrics |
| `reconstruct/reconstruction.npz` | reconstruct | `K`, `image_names`, `rotations`, `translations`, `points`, and `colors` if present |
| `localize/query_pose.npz` | localize | `R`, `t`, and `K` if present |
| `colmap/{cameras,images,points3D}.txt` | colmap | COLMAP's text model, image names without extension |
| `evaluate/evaluation.json` | evaluate | `reference`, `scale_image` |
| `dense/fused.ply` | dense | served as it is; the browser parses it |

A run missing some of these shows what it has. Outputs of `localize` and
`evaluate` older than the reconstruction are ignored: they describe the one
before.

## Inside

Ports and adapters, checked by import-linter rather than merely described:

```
src/sfmview/
├── domain/      values (RunId, Camera, Model, Scene) and frames.py; no I/O
├── ports.py     RunStore and StepSource: the interfaces the API needs
├── adapters/    runs_fs.py, colmap_text.py, sfmkit_files.py,
│                redis_steps.py and memory_steps.py
├── api/         create_app(store, steps), the routes, the WebSocket, the schemas
├── web/         index.html, style.css, js/{main,api,live,ui,scene,geometry}.js
└── main.py      the composition root: settings, adapters, uvicorn
```

The API sees the ports and never an adapter, so its tests run against a store
and a stream in memory; another source of runs, or another broker, is a new
adapter and nothing else. Both `StepSource`s pass one suite — Redis's when a
server is given, as CI does.
