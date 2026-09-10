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
- [ ] **`sfmkit run --help` should list the stages** in order, one line each. A
  newcomer cannot tell the order from `sfmkit --help`.

## Docker

- [ ] **Non-root user.** Files the container creates in a mounted `runs/` belong to
  root.
- [ ] **`match` inside a container.** The image has no PyTorch. Options: CPU
  PyTorch in the current image (a few hundred MB), and/or a GPU image; one
  Dockerfile with multi-stage `cpu`/`gpu` targets.
- [ ] **LightGlue downloads its weights** from GitHub on the first `match`. An
  image that runs `match` should carry them.
- [ ] **Publish the image** to a registry, so nobody has to build it.
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
