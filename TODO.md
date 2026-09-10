# TODO

Open work, grouped by area. Move to GitHub Issues once the repository is public.

## Pipeline

- [ ] **Real calibration.** `calibrate` only copies `precomputed/K.txt`: the
  chessboard photos from the course were never kept. The chessboard code exists
  and is tested on synthetic boards; it needs the photos in
  `data/valencia/calibration/`.
- [ ] **Our K is very likely wrong for these photos, by ~17%.** The chessboard
  K (`legacy/.../camera_calibration.py`, photos `calib_*.jpg` since lost) says
  f = 3544, and is self-consistent (its /2, /4, /6 downscaled variants agree).
  Everything else says ~3000-3030: the photos' EXIF (SM-G996B, 5.4 mm, 26 mm
  equivalent, no digital zoom) give 5.4 mm / 1.8 um pixels = ~3000 px and 26 mm
  on the native 4:3 diagonal = ~3028 px; COLMAP self-calibrates to ~3020 from
  its matches and from ours alike. Forcing our K on COLMAP makes it agree *less*
  with a reconstruction that uses the same K (1.44° against 1.03°, max 6.70°
  from identical input). Likely the chessboard photos were taken in another mode
  (crop, stabilisation, video, another lens). Test: reconstruct with the EXIF K
  (f = 3028, principal point at the centre) and see whether the error against
  COLMAP drops. And `calibrate` could read K from EXIF when there is no
  chessboard.
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
- [ ] **Img12 is fragile.** With CPU matches it fails to register (8 cameras,
  1.57°) where GPU matches give 9 cameras and 0.98°. Small differences in the
  matches should not lose a camera.
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
- [ ] **Live visualisation**: the callback is in (`reconstruct(..., on_step=...)`, used
  by the CLI to show each step as it finishes); still to do: a Rerun sink, then a
  three.js viewer served by an `api` service.
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
