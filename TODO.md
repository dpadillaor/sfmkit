# TODO

Open work, grouped by area. Move to GitHub Issues once the repository is public.

## Pipeline

- [ ] **Real calibration.** `calibrate` only copies `precomputed/K.txt`: the
  chessboard photos from the course were never kept. The chessboard code exists
  and is tested on synthetic boards; it needs the photos in
  `data/valencia/calibration/`.
- [ ] **Our K disagrees with COLMAP's self-calibration.** `evaluate` prints both.
  The chessboard K says f = 3544; COLMAP, calibrating from the scene, says ~3020,
  with its own SIFT matches and with sfmkit's alike, so the difference is not the
  features. Either the chessboard calibration (whose photos are lost) is off, or
  the scene does not constrain the focal length well. Scoring the same GPU
  reconstruction (which uses our K) against the four COLMAP variants:
  own matches + own K 1.03° (max 2.62), own matches + our K 1.44° (4.36),
  our matches + own K 1.06° (2.72), our matches + our K 1.52° (6.70). Forcing
  our K on COLMAP makes it agree *less* with a reconstruction that uses the
  same K, even from identical input, while COLMAP's own K converges on ~3020
  from either set of matches. Hypothesis: our K is wrong for these photos;
  `legacy/` holds several phone calibrations (`K_Calibration_12MP*.txt`, a 64 MP
  one), and the one chosen may not match how the photos were taken. Test:
  reconstruct with f ~ 3020 and see whether the error against COLMAP drops.
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
- [ ] **`reconstruct` is silent for ~4 minutes**, printing nothing between the track
  count and the final table, so it looks hung. It should report each step as it
  happens (camera added, points, RMSE, bundle-adjustment time). The `on_step`
  callback planned for live visualisation would give it for free.
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
- [ ] **The `gpu` image.** `ARG TORCH` already picks `requirements-torch-<TORCH>.txt`;
  a `gpu` image needs `requirements-torch-gpu.txt` (CUDA PyTorch, ~5 GB image
  against 1.6 GB for `cpu`), and compose needs the GPU (`gpus: all`, and
  nvidia-container-toolkit on the host). Two images rather than one CUDA image
  that also runs on CPU, so nobody downloads ~4 GB of CUDA they do not use.
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
- [ ] **Install section**: conda (`conda create -n sfmkit python=3.11`, then
  `pip install --no-deps -r requirements-cpu.txt -r requirements.txt` and
  `pip install --no-deps -e .`) and Docker are the only supported installs.
- [ ] Mention `sfm.device` and that CPU and GPU give slightly different matches.
- [ ] A GIF of the reconstruction growing, once live visualisation exists.

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
- [ ] **Live visualisation**: a callback in `reconstruct`, a Rerun sink, then a
  three.js viewer served by an `api` service.
- [ ] **Dense reconstruction, optional, gpu image only.** COLMAP's MVS
  (`patch_match_stereo`, then fusion to a point cloud) needs CUDA, so
  `pycolmap-cuda12`. Not needed to compare cameras; a dense cloud would suit the
  live viewer and Gaussian splatting.
- [ ] **COLMAP-format exporter**, so a reconstruction can feed Gaussian splatting.
- [ ] `scripts/` still do `sys.path.insert(0, "src")`, unnecessary now that the
  package is installed.

## Housekeeping

- [ ] Delete `legacy/` when nothing in it is needed any more.
- [ ] Delete `../MGRCV-history-backup-2026-09-10.bundle` (history before the
  purge of the course code) once sure it is not needed.
