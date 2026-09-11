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
  (2) done: `calibrate.exif: true` takes K from the photos' EXIF (f = 3028.7),
  used by `configs/valencia/9cameras-exif.yaml`; the other configs still use the
  chessboard K, to compare; (3) regenerate the example run and the README
  numbers, from the EXIF K or the new chessboard one.
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
  scene's cameras are unchanged (0.311° against 0.312°). What is left of this
  item: the precomputed course model (`examples/`, `9cameras`) still has the
  query's principal point pinned, so its 13.7° stands until it is regenerated.
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
Done: `packages/viewer` (`sfmview`) draws finished runs (sfmkit's model,
COLMAP's and the dense cloud, in one frame) and follows a run live through Redis
Streams, with a timeline to rewind it; sfmkit publishes when `SFMKIT_BROKER` is
set; `contracts/step.schema.json` defines the messages. `docs/viewer.md` has
the contract, the API and the architecture.

- [ ] **Docker, the user's lesson**: the viewer's Dockerfile (done: listens on
  `0.0.0.0` through `SFMVIEW_HOST`), the compose service `viewer` (done:
  `ports`, `runs/` and `data/` read-only, seen through an SSH tunnel), and the
  service `redis`, still to do, one concept at a time, each with a fictitious
  example first: compose's default network and DNS by service name; `ports`
  (host to container, `127.0.0.1:8000:8000` for the browser) against no ports
  (container to container: `redis` needs none); `depends_on` with a
  `healthcheck` (`/api/health`); the broker URL as an environment variable
  (`SFMKIT_BROKER=redis://redis:6379` in `cli`, `SFMVIEW_BROKER` in `viewer`);
  `runs/` mounted read-only in the viewer; what happens when a service dies
  mid-run (sfmkit carries on; the viewer retries every 2 s). The build context
  is the root, as sfmkit's. Inside a container the viewer listens on
  `SFMVIEW_HOST=0.0.0.0`. The redis-py added to sfmkit's requirements means the
  sfmkit image must be rebuilt.
- [ ] **sfmkit's points have no colour.** `reconstruction.npz` holds K, poses,
  points and tracks; COLMAP's model has colours, ours none. The viewer draws
  each sparse model in one colour anyway, to tell them apart, but a "true
  colours" switch would need them: sample each point's colour from an image that
  observes it and save it as `colors` (the viewer already reads the key).
- [ ] **Streams never expire.** A run's stream stays in Redis until the run is
  repeated (a `start` empties it), which is what lets a finished run be
  rewound; with many runs, set an `EXPIRE` after the `end` (a week?).
- [ ] **Live steps on a run with no finished model** are drawn in sfmkit's world
  frame (the seed pair's first camera), not the reference camera's, as the
  transform comes from the finished model. Harmless, as nothing else is drawn
  then; the `start` message could carry the reference to fix it.
- [ ] **The end of a watched run reloads the whole scene**, dense cloud included
  (3.7 MB on Valencia), though only sfmkit's files changed.
- [ ] **Only `reconstruct` publishes.** `sfmkit run` could publish each stage's
  start and end too, so the page shows where a whole run is; the TUI could read
  the same stream instead of parsing the CLI's output.
- [ ] **three.js comes from jsDelivr** (pinned, 0.170.0, through an import map),
  and IBM Plex from Google Fonts, so the page needs the internet. For offline
  use, keep them in `web/vendor/` (tracked, with their licences: MIT and OFL)
  and point the import map and the CSS there. Small: `three.module.min.js` is
  0.69 MB, OrbitControls and PLYLoader 0.05 MB, the fonts well under 1 MB,
  against an image of about 250 MB. It also stops the page telling Google and
  jsDelivr who opens it.
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
- [ ] **Three copies of "find the file of an image"** in `data/features.py`,
  `apps/cli/changes.py` and `apps/cli/figures.py`: replace them with
  `data.io.image_file`, which also refuses ambiguous names (`Img02.jpg` and
  `Img02.png`).
- [ ] **A figure of the dense cloud.** The `dense` stage writes `dense/fused.ply`
  (137 650 points on Valencia, 3 min on an RTX 4090); `figures` does not draw it
  yet, and it would make the README's best picture. The viewer draws it
  (`docs/figures/viewer.png`); it could also feed Gaussian splatting.
- [ ] **A mesh of the dense cloud.** `fused.ply` is points only, which the viewer
  draws but mesh viewers (3dviewer.net) refuse: "no faces". COLMAP can mesh it
  (`pycolmap.poisson_meshing`), as an option of the dense stage.
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

## Housekeeping

- [ ] Delete `legacy/` when nothing in it is needed any more.
- [ ] Delete `../MGRCV-history-backup-2026-09-10.bundle` (history before the
  purge of the course code) once sure it is not needed.
