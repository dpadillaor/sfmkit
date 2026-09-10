# TODO

Open work, grouped by area. Move to GitHub Issues once the repository is public.

## Pipeline

- [ ] **Real calibration.** `calibrate` only copies `precomputed/K.txt`: the
  chessboard photos from the course were never kept. The chessboard code exists
  and is tested on synthetic boards; it needs the photos in
  `data/valencia/calibration/`.
- [ ] **Run COLMAP for real, with pycolmap.** `colmap` only copies a precomputed
  model; pycolmap 4.2.0 is now in the image. Agreed config, following the same
  rule as `calibrate` (precomputed if given a file, computed otherwise):
  ```yaml
  colmap:
    precomputed: precomputed/colmap   # copy a model; COLMAP does not run
    # or
    matches: colmap   # COLMAP's own SIFT, matching and mapping: the independent
                      # reference; three pycolmap calls, ~12 s on CPU
    # or
    matches: sfmkit   # COLMAP's mapper only, fed the keypoints and matches from
                      # verify through its database, as the course did: same
                      # input, so it compares the reconstruction alone
  ```
  Done: the config (`colmap.model` is now `colmap.precomputed`), checked when
  loaded: both keys at once, or another `matches` value, is an error; neither
  is an error when the stage runs, as in `calibrate`. To do: the two
  `matches` modes in the stage. Whatever the variant, the stage leaves
  `colmap/{cameras,images,points3D}.txt` (from the largest model if COLMAP
  splits the photos), so `evaluate` and `figures` do not change. Open: our K
  from `calibrate` or COLMAP's own (the fair choice for `sfmkit` is ours);
  whether to keep `database.db` in the run.
- [ ] **Compare the intrinsics.** COLMAP self-calibrates (the course model: f =
  3047) while our K says 3544. Reporting both K side by side in `evaluate` would
  show how far apart the calibrations are, and whether it matters.
- [ ] **The COLMAP reference is not independent.** The course built it with
  `feature_importer` and `matches_importer` (`legacy/.../colcommands.txt`): COLMAP
  was given the course pipeline's own SuperPoint + LightGlue matches, RANSAC
  inliers, reference pairs only, and ran just `mapper`, self-calibrating
  (f = 3047). So 0.981° compares our reconstruction with COLMAP's on similar
  matches, not with an independent reference. A full COLMAP run (its own SIFT
  features and matching) would be. Say so in the README until then.
- [ ] **Review how the old photo (the query) is treated, stage by stage.** It is
  handled differently almost everywhere: `match` pairs it with the reference
  only, even when `exhaustive: true`; `reconstruct` leaves it out on purpose;
  `localize` uses DLT as its camera is unknown; `changes` compares it with the
  reference. And **`evaluate` never scores it**: it compares the reconstructed
  cameras only, while `localize/query_pose.npz` is never checked against
  COLMAP's pose for Img00, which the model has. The project's own question goes
  unmeasured.
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

- [ ] **The dev conda env is not the reference environment.** `mgrcv-sfm` is
  Python 3.10 with CUDA PyTorch; the requirements are frozen for 3.11 (scipy
  1.17 needs it). Recreate it from the requirements files, as the README will
  tell everyone to, with a `requirements-gpu.txt` for the GPU.
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
