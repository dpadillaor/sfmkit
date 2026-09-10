# sfmview, the viewer

A web page that draws a run in 3D: sfmkit's reconstruction, COLMAP's, the old
photo as each of them placed it, and COLMAP's dense cloud. It is its own
package, `packages/viewer/`, with its own dependencies and image, and it does
not import sfmkit: the two share files, described below, and nothing else.

![The viewer on valencia/9cameras-dense](figures/viewer.png)

## Running it

```bash
conda create -n sfmview python=3.11
conda activate sfmview
cd packages/viewer
pip install --no-deps -r requirements.txt -r requirements-dev.txt
pip install --no-deps -e .
cd ../..
sfmview --runs runs        # http://127.0.0.1:8000
```

`--runs`, `--host` and `--port`, or `SFMVIEW_RUNS`, `SFMVIEW_HOST` and
`SFMVIEW_PORT` in a container. The page loads three.js from jsDelivr, so the
browser needs the internet.

## What it reads: the contract with sfmkit

A run is `runs/<project>/<config>/`, one directory per stage. The viewer only
reads, and only these:

| File | Stage | What the viewer takes |
|---|---|---|
| `*/manifest.json` | every stage | `stage`, `timestamp`, `config` (`sfm.reference`, `localize.query`); from `evaluate`'s, `mean_rotation_error_deg`, `max_rotation_error_deg`, `n_cameras`, `query_rotation_error_deg` |
| `reconstruct/reconstruction.npz` | reconstruct | `K` (3×3), `image_names` (N), `rotations` (N×3×3), `translations` (N×3), `points` (M×3); `colors` (M×3, uint8) if present |
| `localize/query_pose.npz` | localize | `R`, `t`; `K` if present |
| `colmap/{cameras,images,points3D}.txt` | colmap | COLMAP's text model, image names without extension |
| `evaluate/evaluation.json` | evaluate | `reference`, `scale_image` |
| `dense/fused.ply` | dense | served as it is; the browser parses it |

Poses are world to camera, `x_cam = R X + t`, in OpenCV's axes: x right, y down,
z forward. A run missing some of these shows what it has.

## One frame for two reconstructions

Each reconstruction has its own origin, orientation and scale. The viewer
brings them together as sfmkit's `evaluate` does, so what it draws is what is
scored: both are expressed in the reference camera's frame, and COLMAP's is
scaled so that `scale_image` sits as far from the reference as it does in
sfmkit's. The shared frame is sfmkit's reference camera, at sfmkit's scale; the
dense cloud, being COLMAP's, takes COLMAP's transform. The server sends each
model in its own coordinates with the 4×4 that moves it
(`sfmview/domain/frames.py`); the page converts OpenCV's axes to three.js's in
one place (`web/js/scene.js`).

## The API

| Route | |
|---|---|
| `GET /api/health` | `{"status": "ok"}` |
| `GET /api/runs` | every run: stages, layers (`sfmkit`, `colmap`, `dense`), metrics |
| `GET /api/runs/{project}/{config}/scene` | the models, with cameras, flat point arrays and their transforms |
| `GET /api/runs/{project}/{config}/dense.ply` | the dense cloud |
| `GET /docs` | the API, from FastAPI |

Names are checked as single path components, and a run directory must lie
inside the runs root, symlinks included.

## Inside

Ports and adapters, checked by import-linter (`packages/viewer/pyproject.toml`):

```
src/sfmview/
├── domain/      values (RunId, Camera, Model, Scene) and frames.py; no I/O
├── ports.py     RunStore, the one interface the API needs
├── adapters/    runs_fs.py (RunStore over runs/), colmap_text.py, sfmkit_files.py
├── api/         create_app(store), the routes, the JSON schemas
├── web/         index.html, style.css, js/{main,api,ui,scene,geometry}.js
└── main.py      the composition root: settings, adapters, uvicorn
```

The API sees `RunStore` and never an adapter, so its tests run on a store in
memory; a new source of runs is a new adapter and nothing else.
