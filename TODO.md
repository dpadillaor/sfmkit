# TODO

Open work, grouped by area. Move to GitHub Issues once the repository is public.

## Pipeline

- [x] **Img28 was shot with 1.17x digital zoom** (EXIF `DigitalZoomRatio`),
  which a phone leaves out of the 35 mm equivalent focal length: its K was 17%
  short, f 3544 against the others' 3029, and it was the worst camera of every
  run (1.4-1.8°, the rest 0.02-0.42°). 3029 x 1.17 = 3543.5, the course's
  chessboard K to 0.1 px: the chessboard was photographed zoomed, and was
  right for zoomed photos. `calibrate.exif` now reads the zoom and refuses
  photos whose zoomed focal lengths differ. Img28 is gone from the scene; Img07
  (unused before) and five photos of the same session, same setting, are in:
  Img02 and Img08-Img11, named by capture time. Seven more of that session, at
  64 MP (9248x5204, 5.9 mm, 27 mm equivalent: another of the phone's cameras,
  f ~7214 px), and one more zoomed 1.17x, were left out: they need a K each.
- [ ] **Check the K with a chessboard.** K comes from the photos' EXIF
  (SM-G996B, 26 mm equivalent: f = 3029 px, principal point at the centre),
  and COLMAP's self-calibration (~3020) agrees. The course's chessboard K,
  `precomputed/K.txt` (f = 3544), was ~17% too long, and its photos are lost.
  `calibrate` still takes chessboard photos (tested on synthetic boards) or a
  K file: photos in the scene's mode (main lens 1x, 16:9, 4032x2268) in
  `data/valencia/calibration/` would check the EXIF K.
- [x] **The README says what the error is measured against** (2026-09-13). Both configs
  score the reconstruction against COLMAP run from scratch on the same photos,
  its own features and matching: the two share the photographs and nothing
  else, which is what makes 0.35° (cpu) and 0.29° (gpu-dense) worth quoting.
  Scored instead against the course's model, which was fed matches like ours,
  the same reconstruction read 0.379°. COLMAP varies between runs, but
  negligibly on the scene's cameras (±0.002°, over 3 runs); its placement of
  the old photo does not, as `docs/old-photo.md` says.
- [x] **`sfmkit run --help` should list the stages** in order, one line each. A
  newcomer cannot tell the order from `sfmkit --help`.

## Docker

- [x] **Plain `docker run` runs as uid 1000**, not as root: both images create
  the user and switch to it, and `/app` belongs to it. Compose still overrides
  it with the caller's own uid, so runs written to a mounted `runs/` belong to
  whoever started them.
- [x] **`make shell`**: a shell inside the image with a run's mounts,
  `DEVICE=gpu` for the other one.
- [x] **Name of the compose service.** It was in doubt because `cli` also ran
  the TUI; with the TUI gone, `cli` is exact again.

## Using it on your own project

- [ ] **Three mounts per project** (`data/`, `configs/`, `runs/`). Easy to get one
  wrong; a project-first layout was floated, not decided.
- [ ] **A project template**: the folder shape and a starting config.

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
- [x] **True colours for sfmkit's points: cancelled** (2026-09-12). Each point
  could take the colour of a pixel that sees it (the viewer already reads a
  `colors` key, and COLMAP's model carries them), but one colour a model is
  what tells the two apart on screen, which is the point of drawing both.
- [x] **A documentation site**, MkDocs Material from `docs/*.md`, on GitHub
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
  start and end too, so the page shows where a whole run is; a reporting tool
  could read
  the same stream instead of parsing the CLI's output.
- [x] **three.js and the fonts are in `web/vendor/`** (three 0.170.0, 0.74 MB
  with OrbitControls and PLYLoader, MIT; IBM Plex Sans and Roboto Mono, one
  variable file a family, 0.14 MB, both OFL), so the page needs no network and
  tells Google and jsDelivr nothing. Checked with every outside host blocked:
  it asks for its own server only.
- [x] **Tests for the page's JavaScript: cancelled** (2026-09-12). `geometry.js`
  is pure and would test well, but only with Node in the toolchain, which is
  otherwise Python alone. The page is checked by screenshots from headless
  Chrome over the DevTools protocol (`--use-angle=swiftshader`; Chrome's own
  `--screenshot` does not wait for WebSockets).
- [x] **`contracts/check.py` stays as it is** (2026-09-13). Eighty-two lines
  covering the part of JSON Schema the contracts actually use, against a
  dependency in both packages' environments -- and in both images -- for five
  message shapes. Revisit only if `jsonschema` arrives for some other reason,
  or if the schemas start using what it does not cover.
- [x] **pre-commit checks both packages' layering** (2026-09-13), through
  `tools/lint-imports`: import-linter has to import a package to follow its
  imports, and the hooks run in whichever environment the commit is made from,
  so each package is checked when it is installed there and skipped, out loud,
  when it is not. CI builds both environments, so nothing is skipped twice.
- [x] **The viewer's tests are on httpx2** (2026-09-13), so the warning is
  gone rather than filtered. httpx2 2.12.0 brings `httpcore2` and `truststore`
  and drops `certifi`; all four are pinned in `requirements-dev.txt` and the
  80 tests pass in an environment built from it alone. Rebuild `sfmview` (or
  `pip install --no-deps -r packages/viewer/requirements-dev.txt`) after
  pulling this. Only the tests used httpx: nothing the viewer serves changed.
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

- [x] **Rewritten** (2026-09-13): it opens with the question the project
  answers, gives the old photograph and the change map a section of their own
  rather than two rows in a table of ten, and carries Try it, the viewer, what
  is inside, the badges and the links to the site.
- [x] **`README.old.md` is folded in and gone** (2026-09-13). What it held and
  the site did not: the camera estimated for the old plate against COLMAP's own
  estimate of it, now in `docs/old-photo.md` and measured again on today's run
  (f 552.0/555.8 against 553.8, six pixels apart in the centre, and the course's
  3.8:1 K beside them); how far the change figure can be read, now on the
  results page; and the diagnostics figures, now in the run guide with the
  reading that made them worth showing. `matches`, `epipolar`, `residuals` and
  `changes` went from 1-2.5 MB PNGs to resized JPEGs on the way.
- [x] **The README mentions `sfm.device`** (2026-09-13), and that a CPU and a
  GPU find slightly different matches and so give slightly different numbers.

## Going public

- [x] **MIT licence**, with a `NOTICE` for what it does not cover: the
  photographs, SuperPoint's weights, COLMAP, the vendored fonts and three.js.
- [x] **The history is the author's own**, under the GitHub no-reply address,
  and carries no co-author trailers. Backups of both states are outside the
  repository: `../MGRCV-history-backup-2026-09-10.bundle` (the course's code,
  tag `baseline-original`) and `../MGRCV-backup-before-rewrite-2026-09-13.bundle`.
- [x] **The repository is up**: `github.com/dpadillaor/sfmkit`, public, `main`,
  189 commits, wiki and projects off, eight topics.
- [x] **Badges in the README**: the checks, the documentation and the licence.
  The published image's version goes up when there is a release to name.
- [x] **The README leads with what the project is for** — the old photograph
  and what changed — instead of burying them in a table of ten stages.
- [x] **`compose.yaml` names the images as they are published**
  (`ghcr.io/dpadillaor/...`), so `docker compose pull` fetches them and nobody
  waits for a build they did not ask for. Builds write the same names.
- [x] **Failures are heard in Discord, not in the inbox** (2026-09-13).
  `.github/workflows/notify.yml` watches the three workflows and posts the ones
  that fail to a Discord channel, with the branch, the commit and a link; it
  says nothing about a green run. It wants the repository secret
  `DISCORD_WEBHOOK` (`gh secret set DISCORD_WEBHOOK`) and passes without it, so
  a fork is not failed by a secret it cannot have. Still to do by hand, and
  only the account's owner can: turn the email off at
  <https://github.com/settings/notifications>, Actions -> Email.
- [ ] **Rehearse the newcomer's path against the published repository**: clone,
  the conda instructions as written, `no-colmap.yaml`, the viewer. It was
  rehearsed against the image; the instructions on the site have not been.

## Docs website

- [x] **MkDocs + Material site in `website/`**, styled to match the viewer, with
  install (conda and Docker), the pipeline, a CLI reference, the configuration,
  what a run holds, the viewer, its HTTP API, its live messages, the results and
  development. `website/requirements.txt` pins it. `mkdocs serve -f
  website/mkdocs.yml`, in an environment of its own or in `sfmview`.
- [x] **The site is live** at `dpadillaor.github.io/sfmkit`, deployed by
  `Documentation` on every push to main.
- [x] **`site_url`, `repo_url`, `repo_name` and `edit_uri` are filled in**
  (2026-09-13): the header carries the repository and its stars, and every page
  an "edit this page" pencil onto `main`.
- [ ] **Publish the images.** `.github/workflows/images.yml` pushes to GHCR and
  to Docker Hub when a release is published; Docker Hub waits on the secrets
  `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`, which could not be set on
  2026-09-13 because GitHub's secret API was answering 500 from both `gh` and
  the web. Retry, then publish the first release.
  When they are up, replace the "Published images" note in
  `website/docs/install/docker.md` with the real `docker pull` lines, and give
  `compose.yaml` an `image:` that can be pulled rather than built.
- [ ] **The GPU image is published by hand**, `make push DEVICE=gpu`, because
  CUDA PyTorch and COLMAP's CUDA build do not fit a hosted runner's disk. The
  target refuses a dirty tree and labels the image with its commit, so it stays
  as traceable as a CI-built one; it still has to be remembered at each release.
  A self-hosted runner with a GPU would fold it back into `images.yml`.
- [ ] Keep the site content in sync with the README once the README rework
  lands: install steps and the stages table are duplicated for now.
- [ ] **The figures are kept twice**, in `docs/figures/` for the README and in
  `website/docs/figures/` for the site, copied by hand: 9 MB of duplicates, and
  one of the two goes stale the first time only one is updated. MkDocs will not
  read outside its own docs directory; the ways out are a build step that
  copies them, a symlink, or moving the figures under `website/` and pointing
  the README at raw URLs.
- [x] **A tutorial**, the page COLMAP's site has and ours did not: one pass
  from a clone to a reconstruction in the viewer, then the same on photographs
  of your own. It is where most readers start.
- [x] **An FAQ** for the four questions that keep coming: whether COLMAP is
  needed, whether a GPU is, where the feature weights come from, and why the
  old photograph is handled apart.
- [x] **A licence page** on the site, saying what MIT covers and what the
  NOTICE carves out.
- [x] **A changelog** (2026-09-13), `CHANGELOG.md` at the root, in Keep a
  Changelog's shape, and on the site under Project -- included from the root
  file by pymdownx.snippets rather than copied, so there is one of it. Its
  first section is Unreleased; it becomes `v0.1.0` when that tag is pushed,
  which is also what publishes the images.

## Later

- [x] **Set aside (2026-09-12): everything downstream of exporting to COLMAP's
  format.** A COLMAP-format exporter would let a reconstruction of ours feed
  Gaussian splatting, be densified by COLMAP, or be meshed by it
  (`pycolmap.poisson_meshing`). None of that is what this project is for: it
  reconstructs, localises an old photograph and measures itself.
- [x] **Imports are at the top now**, except torch's (a second), matplotlib's
  and the TUI's, each with a line saying why (2026-09-12).
- [x] **The dense cloud is drawn** by the `figures` stage, from the reference
  photo and from beside it (`render/viz.plot_dense`, `orbit`), 2026-09-12.
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
