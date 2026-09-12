# TODO

Open work, grouped by area. Move to GitHub Issues once the repository is public.

## Pipeline

- [x] **Img28 was shot with 1.17x digital zoom** (EXIF `DigitalZoomRatio`),
  which a phone leaves out of the 35 mm equivalent focal length: its K was 17%
  short, f 3544 against the others' 3029, and it was the worst camera of every
  run (1.4-1.8°, the rest 0.02-0.42°). 3029 x 1.17 = 3543.5, the course's
  chessboard K to 0.1 px: the chessboard was photographed zoomed, and was
  right for zoomed photos. `calibrate.exif` now reads the zoom and refuses
  photos whose zoomed focal lengths differ. Img28 is gone from the scene; Img16
  (unused before) and five photos of the same session, same setting, are in:
  Img11 and Img17-Img20, named by capture time. Seven more of that session, at
  64 MP (9248x5204, 5.9 mm, 27 mm equivalent: another of the phone's cameras,
  f ~7214 px), and one more zoomed 1.17x, were left out: they need a K each.
- [ ] **Check the K with a chessboard.** K comes from the photos' EXIF
  (SM-G996B, 26 mm equivalent: f = 3029 px, principal point at the centre),
  and COLMAP's self-calibration (~3020) agrees. The course's chessboard K,
  `precomputed/K.txt` (f = 3544), was ~17% too long, and its photos are lost.
  `calibrate` still takes chessboard photos (tested on synthetic boards) or a
  K file: photos in the scene's mode (main lens 1x, 16:9, 4032x2268) in
  `data/valencia/calibration/` would check the EXIF K.
- [ ] **Say in the README what the error is measured against.** Both configs
  score the reconstruction against COLMAP run from scratch on the same photos,
  its own features and matching: the two share the photographs and nothing
  else, which is what makes 0.35° (cpu) and 0.29° (gpu-dense) worth quoting.
  Scored instead against the course's model, which was fed matches like ours,
  the same reconstruction read 0.379°. COLMAP varies between runs, but
  negligibly on the scene's cameras (±0.002°, over 3 runs); its placement of
  the old photo does not, as `docs/old-photo.md` says.
- [ ] **The course never limited keypoints; we do.** Its `matchingPipeline.py`
  passed `{"max_keypoints": 2048}` to SuperPoint, whose parameter is
  `max_num_keypoints`: the unknown name is kept and ignored, so there was no
  limit (4600-5700 keypoints per modern photo, 5073 in Img02). The rewrite used
  the right name, so our runs, and the 0.981°, use 2048. To reproduce the course
  model with `matches: sfmkit`, allow `sfm.max_keypoints: null` (no limit).
  Worth an experiment: does a higher limit change the result, or save Img12?
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

## TUI

- [ ] **Start a new run from a config**, not only re-run a stage of an existing run.
  Agreed boundary: it views, compares and launches existing configs through the
  CLI, showing the exact command; it does not edit configs.
- [ ] Some columns are still cut: `when` in the run list, `stages` in compare.

## Viewer

A web viewer of runs, live while `reconstruct` works. It is also the exercise in
how two containers talk to each other, so the network is the point, not a cost.
Done: `packages/viewer` (`sfmview`) draws finished runs (sfmkit's model,
COLMAP's and the dense cloud, in one frame) and follows a run live through Redis
Streams, with a timeline to rewind it; sfmkit publishes when `SFMKIT_BROKER` is
set; `contracts/step.schema.json` defines the messages. `docs/viewer.md` has
the contract, the API and the architecture.

- [ ] **A named volume for Redis** (`redis-data:/data`), as `docker compose
  down` loses the streams kept in its anonymous one and so every finished run's
  timeline. Put off: a small loss for now, 240 KB a run (see "Streams never
  expire").
- [x] **Lighting up the points a camera sees: cancelled** (2026-09-12). It would
  have meant the scene API carrying, per model, which points each camera
  observes (both models keep it: sfmkit's `track_images`, COLMAP's tracks).
  The frustum drawn out to the scene already answers what a photo covers.
- [ ] **sfmkit's points have no colour.** `reconstruction.npz` holds K, poses,
  points and tracks; COLMAP's model has colours, ours none. The viewer draws
  each sparse model in one colour anyway, to tell them apart, but a "true
  colours" switch would need them: sample each point's colour from an image that
  observes it and save it as `colors` (the viewer already reads the key).
- [ ] **A documentation site**, MkDocs Material from `docs/*.md`, on GitHub
  Pages through Actions once the repo is public: Mermaid diagrams, the viewer's
  OpenAPI embedded, mkdocstrings for sfmkit's reference, and ADRs for the
  decisions taken (Redis, ports and adapters, `--no-deps`, EXIF K...).
- [ ] **A static demo of the viewer** for the portfolio, and to embed in a site:
  save the API's answers for Valencia as files (runs, scene, dense cloud,
  photos, and the steps of the live stream so the timeline still rewinds),
  teach `api.js` to read them, and publish the page on GitHub Pages; an
  `iframe` then carries it anywhere. Measured, so it is small: the page and its
  vendored three.js 0.9 MB, a run's scene 245 KB, the dense cloud 5.9 MB
  (220k points, worth thinning to ~50k), a photo 3.9 MB as it is and ~300 KB
  resized, fetched only when one is looked through.
- [ ] **Document the interfaces with the standards.** HTTP is covered: FastAPI
  serves OpenAPI at `/docs` and `/redoc` (say so in `docs/viewer.md`). The
  messages are not: an AsyncAPI file in `contracts/` for the channels (the
  stream `sfmkit:steps:<run>`, the WebSocket `/live`), who publishes and who
  listens, reusing `step.schema.json`; and a Mermaid sequence diagram of
  browser, viewer, Redis and sfmkit in `docs/viewer.md`.
- [ ] **A page opened while the server had no broker never goes live.** The
  page asks `/api/health` once, at load; restart the server with a broker (as
  when adding Redis to compose) and the open page follows no steps until it is
  reloaded. Seen in the Docker lesson. Fix: while `liveOn` is false, `refresh()`
  asks `/api/health` again and, once live, opens the feed of the open run.
- [ ] **Streams never expire.** A run's stream stays in Redis until the run is
  repeated (a `start` empties it), which is what lets a finished run be
  rewound; with many runs, set an `EXPIRE` after the `end` (a week?). Size,
  measured: valencia/9cameras-exif's stream is 11 messages, 240 KB in Redis's
  memory, 200 KB saved (the run's directory is 99 MB). But each step carries the
  whole model as it stood, not what changed, so a run grows with steps times
  points: a few hundred cameras and 100k points would be hundreds of MB, in
  RAM. Then send the new points only (a `step` with the ids of what moved), or
  cap the points a step carries.
- [ ] **Live steps on a run with no finished model** are drawn in sfmkit's world
  frame (the seed pair's first camera), not the reference camera's, as the
  transform comes from the finished model. Harmless, as nothing else is drawn
  then; the `start` message could carry the reference to fix it.
- [ ] **The end of a watched run reloads the whole scene**, dense cloud included
  (3.7 MB on Valencia), though only sfmkit's files changed.
- [ ] **Only `reconstruct` publishes.** `sfmkit run` could publish each stage's
  start and end too, so the page shows where a whole run is; the TUI could read
  the same stream instead of parsing the CLI's output.
- [x] **three.js and the fonts are in `web/vendor/`** (three 0.170.0, 0.74 MB
  with OrbitControls and PLYLoader, MIT; IBM Plex Sans and Roboto Mono, one
  variable file a family, 0.14 MB, both OFL), so the page needs no network and
  tells Google and jsDelivr nothing. Checked with every outside host blocked:
  it asks for its own server only.
- [ ] **The page's JavaScript has no tests.** `web/js/geometry.js` is pure (camera
  outlines, robust bounds) and could be tested with `node --test` if Node joins
  the toolchain; for now the page is checked by screenshots from headless Chrome
  driven over the DevTools protocol (`--use-angle=swiftshader`; Chrome's own
  `--screenshot` does not wait for WebSockets).
- [ ] **`contracts/check.py` is a small validator** for the part of JSON Schema
  the contracts use, as neither package otherwise needs `jsonschema`. Swap it if
  one joins.
- [ ] **pre-commit checks sfmkit's layering only.** Its hooks run in the current
  environment, and each package lives in its own; CI checks both.
- [ ] **starlette's TestClient warns that `httpx` is deprecated for `httpx2`**;
  the warning is filtered in `packages/viewer/pyproject.toml`. Switch when
  httpx2 is stable, and drop the filter.
- [x] **A K a camera: weighed and set aside** (2026-09-12). Photos of another
  setting (Img28, zoomed 1.17x; the seven 64 MP ones, another of the phone's
  cameras) would need their own K through reconstruct, the bundle, localize and
  evaluate, and COLMAP with a camera a setting rather than `CameraMode.SINGLE`.
  One camera for the lot is the honest model of this dataset: `calibrate`
  refuses photos whose settings differ, so the mistake cannot come back
  quietly.
- [ ] Alternatives weighed and set aside: sfmkit POSTing straight to the viewer
  (simpler, but sfmkit must know the viewer and loses steps when it is not up);
  a `progress.jsonl` the viewer tails (the TensorBoard way, simplest of all, but
  no network to learn from); NATS, RabbitMQ, Kafka or MQTT instead of Redis
  (history needs JetStream; routing first and consumed messages gone; a JVM for
  tens of messages; only the last message kept). Licence: `redis:7-alpine` is
  Redis 7.4, under RSALv2/SSPLv1 (free to use, not to resell as a hosted
  service); Redis 8 adds AGPLv3; redis-py is MIT. Valkey is the BSD fork, same
  protocol and a drop-in image, if that ever matters.

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
- [ ] A GIF of the reconstruction growing: the viewer's timeline, stepped and captured.
- [ ] **Figures for the README**: `changes/overlay_Img00_on_Img02.png` (the old photo
  set into today's square, near-perfect alignment) is the strongest image the
  project makes; with the dense cloud, the two to lead with. Copy reduced
  versions into `docs/figures/` (the full PNGs are ~17 MB).

## Later

- [x] **Set aside (2026-09-12): everything downstream of exporting to COLMAP's
  format.** A COLMAP-format exporter would let a reconstruction of ours feed
  Gaussian splatting, be densified by COLMAP, or be meshed by it
  (`pycolmap.poisson_meshing`). None of that is what this project is for: it
  reconstructs, localises an old photograph and measures itself.
- [ ] **Review the imports inside functions.** Several modules import inside
  functions (torch in `data/features.py`, cv2 and core modules in the CLI
  commands) so they would load without optional packages. Every supported
  install now has them all. Keep the lazy ones only where they save start-up
  time worth having (torch costs 0.6 s, pycolmap 0.1 s).
- [ ] **A figure of the dense cloud.** The `dense` stage writes `dense/fused.ply`
  (137 650 points on Valencia, 3 min on an RTX 4090); `figures` does not draw it
  yet, and it would make the README's best picture. The viewer draws it
  (`docs/figures/viewer.png`); it could also feed Gaussian splatting.
- [x] **The threshold grid search, redone** with the Schur solver, the EXIF K
  and fourteen photographs (64 combinations, 2026-09-12): the chosen values
  came out as good as anything on the grid, so nothing changed.
  `docs/optimizations.md` 1.6 has the table and what the second search says
  about each threshold.
- [x] **Speed up bundle adjustment: the method, not the hardware.** Done as a
  second solver, `sfm.bundle_solver: schur` (`core/bundle_schur.py`): analytic
  Jacobian, Schur complement, our Levenberg-Marquardt; bundles of 0.1-0.9 s
  instead of 5-42 s. Measurements in `docs/optimizations.md` 1.4. The notes
  below are what led to it. A full run
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
## Housekeeping

- [ ] **What is left of `legacy/`, checked piece by piece (2026-09-12).** Every
  algorithm is rewritten; what has no equivalent is mostly figures:
  - **Done: the old photo's camera is refined after RANSAC**
    (`core/localize.refine_camera`, `localize.refine: none | pose | camera`).
    RANSAC's fit is linear and algebraic; this minimises the pixels, robustly.
    On Valencia the median reprojection falls 14.1 -> 2.0 px, the spread of the
    camera's centre over 20 seeds 0.235 -> 0.031 (the instability that item
    complained of), the error against COLMAP 1.60 -> 1.32° (cpu) and
    0.91 -> 0.66° (gpu-dense), and the estimated principal point moves towards
    COLMAP's (cy 326.8 -> 330.0, COLMAP 340.6). Watch out: a point behind the
    camera cannot be projected, and counted as no error at all it makes turning
    the camera around free -- it now costs, with a test to keep it so.
    (`core/bundle*.py` zeroes those residuals too, which a gauge and many
    cameras make harmless; worth a look one day.)
  - **Worth doing, still.** A point-to-point RMSE between two clouds
    (`sfm.py:502`), and real-world scale from a known distance (two tower
    points 120 m apart, `groundtruth.py:381-420`), which would put the old
    photographer at so many metres rather than so many units. Both were judged
    not worth it on 2026-09-12: the viewer shows the clouds agree.
  - **Figures.** Camera axes drawn as triads (`sfm.py:457`, the viewer shows
    orientation instead), the four candidate poses of an essential matrix
    (`sfm.py:436`), before and after the bundle overlaid (`sfm.py:954`;
    `reconstruct` keeps `before_refinement` unused), the epipoles themselves
    and the click-an-point epipolar viewer (`sfm.py:163-305`).
  - **Not worth it.** Group-structured pair lists (`matchingPipeline.py`,
    superseded by exhaustive or star), a text dump of poses
    (`gtFunctions.py:90`), our F against OpenCV's (`ransac_filter.ipynb`),
    `CALIB_ZERO_TANGENT_DIST` and undistortion, which legacy never applied
    either. `legacy/repro/` is migration scaffolding, not course code.
- [ ] **Keep the history bundle beside the repository safe.** With legacy/
  deleted (2026-09-12, 278 MB: the course's code, the migration scaffolding and
  old outputs) ../MGRCV-history-backup-2026-09-10.bundle is the only copy of
  the course's code, under the tag baseline-original; worth a second copy off
  this machine, and not to be deleted. Gone with it, in no backup: the re-run
  of the original pipeline whose measured numbers docs/optimizations.md quotes.
