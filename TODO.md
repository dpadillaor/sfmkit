# TODO

Open work, grouped by area. Move to GitHub Issues once the repository is public.

## Pipeline

- [ ] **Real calibration.** `calibrate` only copies `precomputed/K.txt`: the
  chessboard photos from the course were never kept. The chessboard code exists
  and is tested on synthetic boards; it needs the photos in
  `data/valencia/calibration/`.
- [ ] **Run COLMAP for real.** `colmap` only copies a precomputed model. To decide:
  pycolmap (pip, same image) or the official binary (`colmap/colmap` image, GPU
  SIFT, its own compose service); fixed K from `calibrate` (fair comparison) or
  self-calibration (current model: f = 3047 against our 3544). It depends only on
  the photos and K, so it could run alongside the match chain.
- [ ] **Img12 is fragile.** With CPU matches it fails to register (8 cameras,
  1.57°) where GPU matches give 9 cameras and 0.98°. Small differences in the
  matches should not lose a camera.
- [ ] **Two OpenCVs after `pip install ".[match]"`.** LightGlue (now installed from
  its GitHub archive, as it is not on PyPI) asks for `opencv-python`, the GUI
  build, which lands beside `opencv-python-headless`. Fine on a desktop; on a
  machine without libGL `import cv2` fails. The image avoids it with `--no-deps`.
  Options: depend on `opencv-python` in `pyproject.toml` (the image does not read
  those dependencies), or document a fix-up.
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
- [ ] **`match` without PyTorch fails with a bare `ModuleNotFoundError: No module
  named 'torch'`.** It should say that `match` needs the `[match]` extra, and that
  the image continues from a saved run with `--from verify`.
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
- [ ] Mention `sfm.device` and that CPU and GPU give slightly different matches.
- [ ] A GIF of the reconstruction growing, once live visualisation exists.

## Later

- [ ] **Live visualisation**: a callback in `reconstruct`, a Rerun sink, then a
  three.js viewer served by an `api` service.
- [ ] **COLMAP-format exporter**, so a reconstruction can feed Gaussian splatting.
- [ ] `scripts/` still do `sys.path.insert(0, "src")`, unnecessary now that the
  package is installed.

## Housekeeping

- [ ] Delete `legacy/` when nothing in it is needed any more.
- [ ] Delete `../MGRCV-history-backup-2026-09-10.bundle` (history before the
  purge of the course code) once sure it is not needed.
