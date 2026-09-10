# TODO

Open work, grouped by area. Move to GitHub Issues once the repository is public.

## Pipeline

- [ ] **Real calibration.** `calibrate` only copies `precomputed/K.txt`: the
  chessboard photos from the course were never kept. The chessboard code exists
  and is tested on synthetic boards; it needs the photos in
  `data/valencia/calibration/`.
- [ ] **Our K is wrong for these photos, by ~17%: confirmed.** The chessboard K
  (`legacy/.../camera_calibration.py`, photos `calib_*.jpg` lost, never pushed
  to ipastore/MGRCV either) says f = 3544, self-consistent but at odds with
  everything else: the photos' EXIF (SM-G996B, 5.4 mm, 26 mm equivalent, no
  zoom) give ~3000-3028 px and COLMAP self-calibrates to ~3020. Reconstructing
  with the EXIF K (f = 3028.4, principal point at the centre), same GPU
  matches, same code: final reprojection 7.11 -> 5.10 px, 1699 -> 1854 points,
  and against the same COLMAP models the mean rotation error falls ~4x:
  1.06 -> 0.26° (GPU SIFT), 1.03 -> 0.22° (CPU SIFT), 0.98 -> 0.30° (course
  model); max 2.7 -> 0.5-1.0°; Img12 no longer the worst. The old photo only
  improves 13.7 -> 11.7° (its own problem, see the query item).
  To do: (1) recalibrate with the chessboard, photos taken in the same mode as
  the scene (main lens 1x, 16:9, 4032x2268), kept in data/valencia/calibration/;
  (2) meanwhile, a `calibrate` source that reads K from EXIF, and use it in the
  configs; (3) regenerate the example run and the README numbers.
- [ ] **Independent reference: 1.041°, first run.** The course's COLMAP model
  was fed the course's own matches, so 0.981° against it was not independent.
  `configs/valencia/9cameras-colmap.yaml` (`matches: colmap`: COLMAP's own SIFT
  and matching) scores the same GPU reconstruction at **1.041° mean, 2.680° max**,
  with the same cameras worst (Img12, Img23, Img14). COLMAP varies between runs,
  but negligibly (±0.002° on that mean, measured over 3 runs). Say it in the
  README.
- [ ] **Review how the old photo (the query) is treated, stage by stage.** It is
  handled differently almost everywhere: `match` pairs it with the reference
  only, even when `exhaustive: true`; `reconstruct` leaves it out on purpose;
  `localize` uses DLT as its camera is unknown; `changes` compares it with the
  reference. And **`evaluate` never scores it**: it compares the reconstructed
  cameras only, while `localize/query_pose.npz` is never checked against
  COLMAP's pose for Img00, which the model has. (Now done: `evaluate` scores
  the query against COLMAP's, apart from the other cameras.)
  **First measurement (2026-09-10), by hand:** localize's Img00 differs by
  ~14° in orientation from both COLMAP placements (13.6° from the new SIFT one,
  13.9° from the course's), while the two COLMAPs agree within 0.8° despite
  different features and procedures. localize is unstable too: across its 20
  seeds the centre spreads 0.27 along one axis (0.02 along the others) and one
  seed reaches 20 px. Hypothesis to test: DLT, which estimates the whole camera,
  degenerates when the 3D points are nearly coplanar, and the old photo sees
  mostly the facade.
  **Strong hint:** `evaluate` now prints the K. localize's DLT puts Img00's
  principal point at cy = 369 in a 418 px tall image (centre 209, COLMAP 209):
  160 px off, vertically. An offset principal point is a tilt in disguise, and
  atan(160 / 647) = 13.9°, against the 13.6° disagreement. Fixing the principal
  point at the image centre (estimating focal and pose only) is the obvious
  experiment.
- [ ] **The course never limited keypoints; we do.** Its `matchingPipeline.py`
  passed `{"max_keypoints": 2048}` to SuperPoint, whose parameter is
  `max_num_keypoints`: the unknown name is kept and ignored, so there was no
  limit (4600-5700 keypoints per modern photo, 5073 in Img02). The rewrite used
  the right name, so our runs, and the 0.981°, use 2048. To reproduce the course
  model with `matches: sfmkit`, allow `sfm.max_keypoints: null` (no limit).
  Worth an experiment: does a higher limit change the result, or save Img12?
- [ ] **Img12 is fragile**, partly because of the wrong K: with the EXIF K it is no
  longer the worst camera. Recheck with CPU matches once K is fixed.
- [ ] **`sfmkit run --help` should list the stages** in order, one line each. A
  newcomer cannot tell the order from `sfmkit --help`.

## Docker

- [ ] **Plain `docker run` still runs as root.** Compose now runs as the user from
  `.env` (`make env`); without compose, files written to a mounted `runs/` belong
  to root unless `--user "$(id -u):$(id -g)" -e HOME=/tmp` is given. Fix: a
  default non-root user in the Dockerfile (`sfmkit`, UID 1000, with a home), so
  plain `docker run` is not root and is right for the common UID 1000; compose
  keeps overriding it from `.env` (optional: without it compose uses 1000). Then
  document it in the README's "Try it".
- [ ] **The `cpu` image cannot reproduce 0.981° from scratch**: its CPU matches
  give 8 cameras and 1.574°, as CPU matches do outside Docker. The saved example
  run (`--from verify`) does give 0.981°. See the Img12 item.
- [ ] **Licence of the SuperPoint weights** baked into the image. They come from
  Magic Leap under terms that restrict use; check them before publishing the
  image to a registry.
- [ ] **Publish the image** to a registry, so nobody has to build it.
- [ ] Cosmetic: a shell in the compose service greets `I have no name!`, as the host
  UID has no entry in the image's `/etc/passwd`. Permissions are unaffected. The
  full fix is an entrypoint script (start as root, `useradd` with `PUID`/`PGID`,
  `exec setpriv` to drop root): ~15 lines, but it replaces `user:`, must cope with
  `--user`, and needs `exec` for signals. Worth it only once others use the image.
- [ ] **`make shell`**: a shortcut for `docker compose run --rm --entrypoint bash cli`.
- [ ] **Name of the compose service.** `cli` also runs the TUI now; `app` or `tool`?

## Using it on your own project

- [ ] **Three mounts per project** (`data/`, `configs/`, `runs/`). Easy to get one
  wrong; a project-first layout was floated, not decided.
- [ ] **A project template**: the folder shape and a starting config.
- [ ] **A second example run?** A CPU run of 9cameras beside the GPU one would show
  `compare` working as soon as a newcomer opens the TUI.

## TUI

- [ ] **Start a new run from a config**, not only re-run a stage of an existing run.
  Agreed boundary: it views, compares and launches existing configs through the
  CLI, showing the exact command; it does not edit configs.
- [ ] Some columns are still cut: `when` in the run list, `stages` in compare.

## Viewer

A web viewer of runs, live while `reconstruct` works. It is also the exercise in
how two containers talk to each other, so the network is the point, not a cost.

- [ ] **Restructure into `packages/`**, one commit that only moves:
  `packages/sfmkit/` (`pyproject.toml`, requirements, `Dockerfile`, `src/`,
  `tests/`) and later `packages/viewer/`, each installed on its own (different
  dependencies, images, lifecycles). `data/`, `configs/`, `examples/`, `runs/`
  stay at the root, shared. To update: CI, `.pre-commit-config.yaml`, the
  Makefile, compose (build context stays the root, so `examples/` can be baked
  in), `pyproject` paths, `CLAUDE.md`, `docs/`, and the four tests that find the
  repo with `Path(__file__).parent.parent`. Check ruff, lint-imports, pytest and
  a Docker build.
- [ ] **The viewer does not import sfmkit.** It would drag in sfmkit's
  dependencies (`sfmkit.data.colmap` imports pycolmap on import) and tie the two
  together. Finished results are read from `runs/`, mounted read-only; the files
  it reads (`manifest.json`, `reconstruction.npz`, COLMAP's text model,
  `fused.ply`: names, keys, units) are a contract written in `docs/`.
- [ ] **Stack of `sfmview`**: FastAPI and uvicorn (HTTP and WebSocket, async,
  pydantic validates messages); `redis.asyncio` (a blocking `XREAD` that does
  not block the server); numpy to turn the npz into JSON. `fused.ply` is served
  as is and parsed in the browser by three.js's `PLYLoader`. Frontend: three.js
  in plain JS, ES modules and an import map, no build step; Vite and TypeScript
  only if it grows (and then a multi-stage Docker build to learn). Tests: pytest
  and FastAPI's `TestClient`, no fake Redis.
- [ ] **Architecture: ports and adapters, lightly.**
  ```
  packages/viewer/src/sfmview/
  ├── domain.py        dataclasses RunId, RunSummary, Scene, Step; no I/O
  ├── ports.py         Protocols RunStore, StepSource
  ├── adapters/        runs_fs.py (RunStore over runs/), redis.py (StepSource
  │                    over Redis Streams), memory.py (StepSource for tests
  │                    and for running without a broker)
  ├── api/             app.py create_app(store, steps); routes.py knows ports only
  ├── web/             index.html, api.js, scene.js, ui.js
  └── main.py          composition root: environment, adapters, uvicorn
  ```
  import-linter: `domain` imports no fastapi, redis or numpy; only
  `adapters/redis.py` imports redis; only `api` imports fastapi; `api` never
  imports `adapters`. SOLID, as it applies: one reason to change per module; a
  new broker is a new adapter and nothing else; the Redis and memory adapters
  pass one test suite, parametrised (Redis's skipped when there is none); two
  small ports, not a "Backend"; `api` depends on Protocols, `main.py` wires the
  concrete ones by plain arguments, no DI framework. Two ports and three
  adapters at most; no service layer until one is needed.
- [ ] **API**: `GET /api/health` (ok and a Redis ping, for compose's
  `healthcheck`); `GET /api/runs` (runs, stages done, metrics from the
  manifests); `GET /api/runs/{project}/{config}/scene` (cameras with name, R, t,
  K; sparse points; colours); `GET /api/runs/{project}/{config}/dense.ply`;
  `WS /api/runs/{project}/{config}/live` (the stream's history, then live
  steps); `GET /` the static page. Validate `project` and `config` against the
  runs that exist (no `../`); `runs/` read-only; bind to `127.0.0.1`.
- [ ] **The contract between sfmkit and sfmview**: `contracts/step.schema.json`
  at the root, versioned (`"v": 1`), the source of truth; each package tests
  against it (sfmkit that what it publishes validates, sfmview that what it
  expects does), so a change on one side breaks a test, not a run. It states the
  coordinate convention: sfmkit's R, t are world to camera, OpenCV axes (x right,
  y down, z forward); three.js has y up and cameras looking down -z; the
  frontend converts in one place, camera centre `C = -Rᵀt`. A step, roughly:
  `{"v": 1, "run": "valencia/9cameras", "step": 3, "image": "Img05",
  "n_registered": 5, "rmse_before": 2.1, "rmse_after": 0.8, "cameras": {...},
  "points": [...], "colors": [...]}`, ~50 KB with 1700 points.
- [ ] **`on_step` carries numbers only.** `core.reconstruct` hands it a
  `StageReport` (step, image, counts, RMSE before and after BA, BA seconds) but
  no poses or points, so a live view cannot draw the model growing. Pass the
  geometry after each step as well.
- [ ] **sfmkit's points have no colour.** `reconstruction.npz` holds K, poses,
  points and tracks; COLMAP's model has colours, ours none, so our cloud would be
  grey. Sample each point's colour from an image that observes it and save it in
  the npz (and in the step message).
- [ ] **Frontend**: `api.js` (fetch, WebSocket), `scene.js` (cloud, cameras as
  frustums, `OrbitControls`), `ui.js` (run list, step panel, a timeline). The
  stream keeps the history, so the timeline can rewind the reconstruction step
  by step: the showpiece for the portfolio.
- [ ] **Live progress through a broker: Redis Streams**, three services `cli`,
  `redis`, `viewer`. sfmkit `XADD`s each step of `on_step` to
  `run:<project>/<config>`; the viewer `XREAD`s from id `0` (the history, so a
  viewer opened late or a reloaded page misses nothing) then blocks for new
  steps and forwards them over WebSocket. Neither service knows the other, only
  `redis`. Cap the stream with `MAXLEN`. Why Redis: streams keep history, no
  configuration, a 40 MB image, `redis-cli XRANGE` shows the messages, widely
  known. Not NATS (history needs JetStream and its concepts), RabbitMQ
  (exchanges, bindings and routing keys first; consumed messages are gone;
  heavier; right for sharing COLMAP jobs among workers), Kafka (JVM, ~1 GB,
  overkill for tens of messages), MQTT (keeps only the last message per topic).
  Valkey is the open-source fork with the same protocol, if Redis's licence
  matters.
- [ ] **Publishing stays optional in sfmkit**: none without `SFMKIT_BROKER`
  (e.g. `redis://redis:6379`); if the broker is down, warn and carry on. One
  function `publish(step)` in `apps/cli`, hung on `on_step`; `core` knows
  nothing. Adds `redis-py` to sfmkit's requirements; a test checks the message
  against `contracts/step.schema.json`.
- [ ] **Docker concepts, one at a time**, each with a fictitious example first:
  compose's default network and DNS by service name; `ports` (host to container,
  `127.0.0.1:8000:8000` for the browser) against no ports (container to
  container); `depends_on` with a `healthcheck`; the broker URL as an
  environment variable; what happens when a service dies mid-run. The user
  writes the viewer's Dockerfile and the compose services.
- [ ] **Order**: the `packages/` move; a fictitious producer and consumer with
  Redis; the viewer listing runs and drawing one finished cloud (with point
  colours in sfmkit); the contract and geometry in `on_step`; then live
  progress and the timeline.
- [ ] Alternatives weighed and set aside: sfmkit POSTing straight to the viewer
  (simpler, a fine first step, but sfmkit must know the viewer and loses steps
  when it is not up); a `progress.jsonl` the viewer tails (the TensorBoard way,
  simplest of all, but no network to learn from).
- [ ] The dense cloud (137k points) is read from `fused.ply` at the end, never
  sent through the broker. A throwaway three.js page embedding it already worked
  (see Later).

## README

- [ ] Sections still to write: **Try it** (the image with the Valencia example),
  **Your own project**, **Development**. Write each once it works.
- [ ] **Install section.** Conda and Docker are the only supported installs, each
  in a CPU and a GPU flavour:
  - Conda, CPU: `conda create -n sfmkit python=3.11`, then
    `pip install --no-deps -r requirements-cpu.txt -r requirements.txt` and
    `pip install --no-deps -e .`.
  - Conda, GPU: the same with `requirements-gpu.txt` instead of
    `requirements-cpu.txt`. Needs an NVIDIA driver for CUDA 12.1 or later (>= 530).
  - Docker, CPU: `make image`, then `docker compose run --rm cli <stage> ...`.
    On Linux, if your UID is not 1000, `make env` first, so the files written
    to `runs/` are yours; a plain `docker run` needs
    `--user "$(id -u):$(id -g)" -e HOME=/tmp` for the same reason.
  - Docker, GPU: `make image DEVICE=gpu`, then `docker compose run --rm cli-gpu ...`.
    The host needs, once: the NVIDIA driver, `nvidia-container-toolkit`
    (from NVIDIA's repository), `sudo nvidia-ctk runtime configure --runtime=docker`
    and a Docker restart. Without them the gpu image still runs, on the CPU,
    and `dense` refuses.
  - Which stages use the GPU: `match` (PyTorch), `colmap` (SIFT), `dense`
    (PatchMatch, GPU only). `reconstruct` runs on the CPU either way.
- [ ] Mention `sfm.device` and that CPU and GPU give slightly different matches.
- [ ] A GIF of the reconstruction growing, once live visualisation exists.
- [ ] **Figures for the README**: `changes/overlay_Img00_on_Img02.png` (the old photo
  set into today's square, near-perfect alignment) is the strongest image the
  project makes; with the dense cloud, the two to lead with. Copy reduced
  versions into `docs/figures/` (the full PNGs are ~17 MB).

## Later

- [ ] **Review the imports inside functions.** Several modules import inside
  functions (torch in `data/features.py`, cv2 and core modules in the CLI
  commands) so they would load without optional packages. Every supported
  install now has them all. Keep the lazy ones only where they save start-up
  time worth having (torch costs 0.6 s, pycolmap 0.1 s).
- [ ] **Three copies of "find the file of an image"** in `data/features.py`,
  `apps/cli/changes.py` and `apps/cli/figures.py`: replace them with
  `data.io.image_file`, which also refuses ambiguous names (`Img02.jpg` and
  `Img02.png`).
- [ ] **A figure of the dense cloud.** The `dense` stage writes `dense/fused.ply`
  (137 650 points on Valencia, 3 min on an RTX 4090); `figures` does not draw it
  yet, and it would make the README's best picture. It could also feed the live
  viewer and Gaussian splatting.
- [ ] **Viewing the dense cloud.** `fused.ply` is points only, so mesh viewers
  (3dviewer.net) refuse it: "no faces". A throwaway three.js page with the cloud
  embedded (2.7 MB for 133k points, orbit controls) worked well: the seed of the
  planned web viewer, and it could be a `figures` output. For mesh viewers,
  COLMAP can mesh the cloud (`pycolmap.poisson_meshing`), as an option of the
  dense stage.
- [ ] **A dense cloud from sfmkit's own model**, not only COLMAP's: needs sfmkit's
  reconstruction written as a COLMAP model (see the exporter under Later).
- [ ] **Speed up bundle adjustment: the method, not the hardware.** A full run
  spends 245 of 267 s in `reconstruct`, whose bundle adjustment
  (`core/bundle.py`) is scipy's generic `least_squares` with a finite-difference
  Jacobian and the iterative `lsmr` solver: 20-35 s an adjustment for 9 cameras
  and ~1700 points, which Ceres solves in well under a second on a CPU. An
  analytic Jacobian and the Schur complement (each observation touches one
  camera and one point), still numpy on the CPU, should bring it to seconds. A
  GPU (a PyTorch rewrite) would only pay with thousands of cameras.
  Options, from most to least our own:
  - **Write the solver**: analytic Jacobian, Schur complement, Levenberg-Marquardt
    loop, in numpy, in `core`. Model and solver both ours; no new dependency;
    tested on synthetic scenes. The recommended one.
  - **Swap scipy for Ceres** (`pyceres`, the COLMAP team's Python bindings): the
    model stays ours, the solver is Ceres, as it is scipy's today. But bindings
    speed up calling Ceres, not what Ceres calls back: a reprojection cost in
    Python is called per observation per iteration, millions of Python calls,
    and throws the speed away. Fast needs the cost in C++, either COLMAP's
    (`pycolmap.cost_functions`, then part of the model is COLMAP's) or our own
    compiled. Another compiled dependency to pin, and the result would move a
    little (another solver converges to a nearby point).
  - **PyTorch on the GPU**: only pays with thousands of cameras. COLMAP itself
    uses its GPU solver from 50 images up only, and pycolmap-cuda12's Ceres is
    built without CUDA anyway (it falls back to the CPU; its mapping takes
    1.6 s on Valencia either way).
- [ ] **COLMAP-format exporter**, so a reconstruction can feed Gaussian splatting.
- [ ] `scripts/` still do `sys.path.insert(0, "src")`, unnecessary now that the
  package is installed.

## Housekeeping

- [ ] Delete `legacy/` when nothing in it is needed any more.
- [ ] Delete `../MGRCV-history-backup-2026-09-10.bundle` (history before the
  purge of the course code) once sure it is not needed.
