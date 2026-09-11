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
- [ ] **A K a camera**, for photos of several settings: per-image K from each
  photo's EXIF (zoom, lens) through reconstruct, the bundle (K fixed per
  camera), localize and evaluate; COLMAP with a camera a setting rather than
  `CameraMode.SINGLE`. It would take back Img28 and the 64 MP photos.
- [ ] **Check the K with a chessboard.** K comes from the photos' EXIF
  (SM-G996B, 26 mm equivalent: f = 3029 px, principal point at the centre),
  and COLMAP's self-calibration (~3020) agrees. The course's chessboard K,
  `precomputed/K.txt` (f = 3544), was ~17% too long, and its photos are lost.
  `calibrate` still takes chessboard photos (tested on synthetic boards) or a
  K file: photos in the scene's mode (main lens 1x, 16:9, 4032x2268) in
  `data/valencia/calibration/` would check the EXIF K.
- [ ] **Independent reference: 0.323°.** The course's COLMAP model was fed the
  course's own matches, so a score against it is not independent.
  `configs/valencia/9cameras-colmap.yaml` (`matches: colmap`: COLMAP's own SIFT
  and matching) scores the reconstruction at **0.323° mean, 1.808° max** (EXIF K,
  Schur solver; 1.041° with the chessboard K and scipy's), against 0.379° for
  the course's model. COLMAP varies between runs, but negligibly on the scene's
  cameras (±0.002° on that mean, measured over 3 runs). Say it in the README.
- [ ] **COLMAP's placement of the old photo is unstable between runs**: the query
  error of the same config against a fresh COLMAP was 1.20°, then 0.97°
  (`9cameras-colmap`) and 3.84° (`9cameras-dense`, the same sparse settings),
  while the scene's cameras agree within 0.03°. Its query pass, one photo of
  another camera registered with the principal point freed, may land in
  different local minima. Measure over several runs, and seed COLMAP if it can
  be.
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
  **Seen in the viewer (2026-09-11):** looking through Img00, both placements
  lay the dense cloud over the old photo about as well; to the eye, sfmkit's a
  little better. The 11.5° is then no misplacement but a trade between K and R:
  on a nearly planar facade a tilt and a shifted principal point project almost
  alike, and each side resolves it its own way. sfmkit's DLT frees the principal
  point (241, 323 in a 557x418 image); COLMAP pins it at the centre (278.5, 209),
  which an old print, perhaps cropped, need not have. So the error against
  COLMAP does not say which is right. Experiments to settle it: localize with
  the principal point fixed at the centre (does it meet COLMAP's R?); COLMAP's
  query pass refining the principal point (does it meet ours?); and both
  poses' reprojection error on one neutral set of 2D-3D matches.
  **Measured the same day, and it points to sfmkit being right:** the vertical
  taken as the direction orthogonal to the nine phones' x axes (held level:
  orthogonal within 0.6°), the phones look up 10-14°, as people photograph a
  facade; sfmkit's Img00 is level (pitch 0.2°, roll 1.5°); COLMAP's looks up
  11.2°. The 11.5° between them is nearly all pitch (axis 0.95 along the
  camera's x). A level camera with the principal point well below the centre is
  how architecture was photographed with view cameras: the rising front shifts
  the lens up to take in a tall facade while keeping verticals parallel (a
  cropped print would do the same). Still a pinhole, only off-centre. COLMAP,
  its principal point pinned at the centre, has to tilt the camera up instead.
  So the query's "error against COLMAP" is COLMAP's, for this photo. **Done:**
  COLMAP's query pass now refines the principal point
  (`ba_refine_principal_point`, the scene's cameras put back afterwards). It
  finds (241, 334) against localize's (241, 323), f 552 against 554-560, the
  camera level (-1.2°), and the query's error falls from 11.5° to 1.2°; the
  scene's cameras are unchanged (0.311° against 0.312°). **Done too** for
  a model made elsewhere: the `colmap` stage refines the query in a precomputed
  model (`refine_query`, the query alone, principal point, focal and distortion
  free), as the course's pinned it. Against the course's model the old photo
  goes 11.9° -> 4.4°, its principal point (278, 209) -> (251, 282); the rest
  of that gap is the model's own matches (a star, the course's keypoints).
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
- [ ] **Light up the points a camera sees**, on hover or when chosen, beside its
  view drawn out to the scene (done): the 3D points its matches made, so how
  well a camera is held shows at a glance (Img28, the worst, against the
  rest). The data exists: sfmkit's `reconstruction.npz` has `track_images`, a
  JSON object a point, image to keypoint; COLMAP's `points3D.txt` has each
  point's track (image ids). The scene API sends neither: add, per model, each
  camera's point indices (or each point's cameras) to the contract in
  `docs/viewer.md`, read them in `sfmkit_files.py` and `colmap_text.py`, and
  colour those points in `scene.js`.
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

- [ ] **Review the imports inside functions.** Several modules import inside
  functions (torch in `data/features.py`, cv2 and core modules in the CLI
  commands) so they would load without optional packages. Every supported
  install now has them all. Keep the lazy ones only where they save start-up
  time worth having (torch costs 0.6 s, pycolmap 0.1 s).
- [ ] **A figure of the dense cloud.** The `dense` stage writes `dense/fused.ply`
  (137 650 points on Valencia, 3 min on an RTX 4090); `figures` does not draw it
  yet, and it would make the README's best picture. The viewer draws it
  (`docs/figures/viewer.png`); it could also feed Gaussian splatting.
- [ ] **A mesh of the dense cloud.** `fused.ply` is points only, which the viewer
  draws but mesh viewers (3dviewer.net) refuse: "no faces". COLMAP can mesh it
  (`pycolmap.poisson_meshing`), as an option of the dense stage.
- [ ] **A dense cloud from sfmkit's own model**, not only COLMAP's: needs sfmkit's
  reconstruction written as a COLMAP model (see the exporter under Later).
- [ ] **Redo the threshold grid search** (`scripts/sweep.py`, optimizations.md
  1.6) with the Schur solver and the EXIF K, the defaults now: its thresholds
  were searched with scipy's solver, which stopped short of every minimum, and
  the chessboard K. With bundles 58x faster the search is cheap.
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
- [ ] **COLMAP-format exporter**, so a reconstruction can feed Gaussian splatting.

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
