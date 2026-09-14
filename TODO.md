# TODO

Open work, grouped by area. The repository is public now, and the backlog
stays here rather than moving to Issues: it is read beside the code, it travels
with the history, and nothing about it needs a browser. An issue tracker can
take from it the day someone else works on this.

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
  `projects/valencia/data/calibration/` would check the EXIF K.
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

- [x] **One Python, 3.11** (2026-09-14). `packages/sfmkit` claimed
  `requires-python = ">=3.10"` and nothing tested it: both images are
  `python:3.11-slim`, both conda environments are 3.11, and every CI job pins
  3.11, as the viewer's `>=3.11` already said. The claim also held the package
  a numpy behind -- numpy 2.3 dropped 3.10, which is why dependabot offered
  sfmkit 2.2.6 and the viewer 2.4.6. Supporting 3.10 for real would mean a
  second set of pinned requirements and a second CI matrix leg; promising it
  without testing it was the worst of both.

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

- [x] **A project is one folder** (2026-09-14). It was spread over three roots
  and its name was written twice -- as the directories and as `dataset:` inside
  the config, with nothing checking the two agreed. Now:

  ```
  projects/valencia/
  ├── data/                 scene/, precomputed/
  ├── configs/              cpu.yaml, gpu-dense.yaml, no-colmap.yaml
  └── runs/
      ├── cpu/              what you write, ignored by git
      └── reference-cpu/    the frozen run, tracked
  ```

  The `dataset:` key is gone: a config lives in `<project>/configs/`, so the
  project is where it sits, and `load_config` refuses one that does not. So are
  `SFMKIT_DATA` and `SFMKIT_RUNS` -- there is no root left to move, and `--out`
  covers writing a run elsewhere. The viewer takes `--projects` instead of
  `--runs` and `--data`. Compose is one mount, writable; what used to be proved
  by `:ro` is proved by the fingerprint check in CI, which holds however anyone
  mounts.

  The frozen runs sit in `runs/` rather than a directory of their own, named
  `reference-*` so that no config can write over one. That is what lets the
  image's copy and the host's be the same tracked file, instead of the image's
  being hidden the moment anyone mounts their own `runs/`.

  `data/precomputed/colmap/15cameras_gpu` is gone: it was byte for byte
  `runs/reference-gpu-dense/colmap`, and `no-colmap.yaml` points there now.

  The regression reproduces exactly: 14 cameras, 2850 points,
  0.3382837616037929 -- the same digits as before the move.
- [ ] **A project template**: the folder shape and a starting config.

## Viewer

A web viewer of runs, live while `reconstruct` works. It is also the exercise in
how two containers talk to each other, so the network is the point, not a cost.
Done: `packages/viewer` (`sfmview`) draws finished runs (sfmkit's model,
COLMAP's and the dense cloud, in one frame) and follows a run live through Redis
Streams, with a timeline to rewind it; sfmkit publishes when `SFMKIT_BROKER` is
set; `contracts/step.schema.json` defines the messages. `docs/viewer.md` has
the contract, the API and the architecture.

- [x] **A named volume for Redis** (`redis-data:/data`): `down` no longer takes
  the streams with it, and so a finished run's timeline survives.
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
- [x] **The interfaces are written down in their own standards.** HTTP was
  already: FastAPI serves OpenAPI at `/docs` and `/redoc`. The messages now have
  `contracts/asyncapi.yaml` (AsyncAPI 3: the stream, the heartbeat, the
  WebSocket, who sends and who listens), pointing at `step.schema.json` rather
  than repeating it — for which the schema's branches were given names under
  `$defs`. And a Mermaid sequence diagram of sfmkit, Redis, the viewer and the
  browser, in `docs/viewer.md` and on the site.
- [x] **A page opened while the server had no broker goes live when one
  appears.** It asked `/api/health` once, at load, so adding Redis to compose
  left the open page following nothing until it was reloaded. `refresh()` asks
  again while there is no broker, and opens the feed of the run on screen the
  moment one answers.
- [x] **Streams expire a week after the run ends** (`live.FINISHED_TTL`), set on
  the `end` or `failed`. They are kept at all so a timeline can be rewound
  afterwards; without an expiry a broker that sees many runs only grows, since
  each step carries the whole model as it stood. How big a step may get is
  capped separately, below.
- [x] **Live steps on a run with no finished model** were drawn in sfmkit's
  world frame — the seed pair's first camera — because the transform came from
  the finished model. The `start` carries the reference camera now, and a step
  is placed by its own copy of it until a finished model has a transform to
  take, so nothing jumps when the run ends.
- [x] **The end of a watched run no longer refetches the dense cloud.** It
  reloaded the whole scene, COLMAP's several MB included, though only sfmkit's
  files had changed; the parsed cloud is now kept and reused while its URL is
  the same, and dropped when a different run's is loaded.
- [x] **Every stage says where the run is.** `sfmkit run` publishes a `stage`
  message at the start and end of each one, and holds the heartbeat for the
  whole run rather than for `reconstruct` alone: a page watching no longer
  looks at nothing for the ten minutes `match` takes. The stream is emptied by
  a run's first message instead of by the `start`, or the reconstruction would
  wipe the stages before it.
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
- [x] **A step's points are capped** (2026-09-13), at `live.MAX_STEP_POINTS`,
  20 000. A step carries the whole model rather than what changed, which is
  what lets the timeline draw any step on its own, but the cost is steps times
  points and it sits in the broker's memory for as long as the stream does.
  Past the cap sfmkit sends a stride through the points -- the model thinned,
  not a corner of it -- and `n_points` still says how many there really are.
  Valencia's 2 830 never reach it. The alternative, a step carrying only the
  points that moved, was not taken: it would make every reader stateful, and
  a viewer that arrives late would have to replay the run to draw it.

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
- [ ] **Transitive pins keep being offered on their own.** Three so far, all
  the same shape: a package that is really another package's half, pinned to
  it by an exact or capped requirement. `pydantic-core` follows pydantic, the
  nvidia wheels and `triton` follow torch, `mpmath` follows sympy which follows
  torch. Each is in dependabot's ignore list as it turns up, and `pip check`
  in CI is what finds the next one -- it has caught two in a day. A rule rather
  than a list would be better, but dependabot has no way to say "only if its
  parent allows it".
- [ ] **numpy 2 and OpenCV 5, one at a time.** Dependabot's first sweep offered
  both inside a list of nineteen, with a CUDA that did not match the pinned
  torch; the config now keeps majors out of the group so each arrives on its
  own. Both are real work: numpy 2 changes promotion rules and copy semantics,
  OpenCV 5 is a major of its own. Take them when there is time to run the
  regression check and read what moved, not on a monthly schedule. Read on
  2026-09-14, against #6 (OpenCV 5), #7 (numpy 2.2.6) and #8 (the viewer's
  numpy 2.4.6):
  - **numpy 2 moves no number here.** No `copy=False` anywhere, no removed
    alias, and `np.ptp` is used as the function, which stays, not the array
    method, which is gone. The saved example gives the same dtypes and the same
    results, run artefacts read across both versions in either direction, and
    the `changes` stage writes byte-identical PNGs. #8 is clean as it stands.
  - **OpenCV 5 moves the pictures, not the numbers.** `solvePnPRansac`,
    `Rodrigues` and `imread` are identical to the bit, so the pipeline's own
    error does not move; but `warpPerspective`'s bilinear was revised and
    `findHomography` finds 79 inliers where it found 78, so the `changes` stage
    reports `changed_fraction` 0.0755479 against 0.0755469 and **every PNG it
    writes has a different hash**. Its figures stop being reproducible against
    the saved example. `findChessboardCorners` and `cornerSubPix` also return
    `(N, 2)` now instead of `(N, 1, 2)`, which this code survives because the
    corners go straight back into OpenCV.
  - **#6 must not go in on its own.** The 5.0 wheel declares `numpy>=2` while
    `requirements.txt` still pins 1.26.4, and everything is installed with
    `--no-deps`, so nothing would ever say so. It goes in with #7 or after it.
  - **#7 offers sfmkit 2.2.6 rather than 2.4.x** because `requires-python` said
    3.10 and numpy 2.3 dropped 3.10. With 3.11 declared, ask dependabot to
    recreate it so both packages sit on one numpy.
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
  `DOCKERHUB_USERNAME` (`padidavid`) and `DOCKERHUB_TOKEN`. They could not be
  set on 2026-09-13, while GitHub's secret API answered 500 from both `gh` and
  the web; that outage is over, so: set them, tag `v0.1.0`, publish the
  release. Then uncomment the `docker pull` lines in
  `website/docs/install/docker.md`, which name the images already.
- [ ] **The GPU image is published by hand**, `make push DEVICE=gpu`, because
  CUDA PyTorch and COLMAP's CUDA build do not fit a hosted runner's disk. The
  target refuses a dirty tree and labels the image with its commit, so it stays
  as traceable as a CI-built one; it still has to be remembered at each release.
  A self-hosted runner with a GPU would fold it back into `images.yml`.
- [ ] Keep the site and the README in step. The rework landed, and the two
  still duplicate the install steps and the stages table; a change to one is a
  change to both until they are cut down to a single home each.
- [x] **The figures are kept once** (2026-09-14), in `website/docs/figures/`.
  They were in two places because MkDocs only reads inside its own docs
  directory, so thirteen files sat duplicated byte for byte -- and the first
  hand-copy had already happened. The README reaches anywhere in the
  repository, so it is the one that moved: its links are relative and GitHub
  resolves them. `docs/figures.md` is the note that used to be that
  directory's README. The tools write there too.
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

- [x] **The frozen example is guarded two ways** (2026-09-14). It is only a
  reference while it was made by the config it names and while nothing writes
  into it. `tests/test_saved_example.py` compares the config each stage records
  in its manifest against the YAML on disk, and names the section that moved;
  CI fingerprints a project's `data/` and its frozen runs around the regression
  run and fails if
  a byte changed. The second one holds however the directories are mounted,
  which compose's `:ro` does not.

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
  - **A point-to-point RMSE between two clouds** (`sfm.py:502`) is still worth
    doing one day; the viewer showing that the clouds agree is why it has
    waited.
  - **Real-world scale from a known distance: dropped** (2026-09-14). A single
    known distance between two reconstructed points fixes the scale and turns
    every unit into a metre -- the old photographer would stand so many metres
    from the facade. The code is four lines. What sinks it is where that
    distance comes from: a monument's published height makes the accuracy of
    everything equal to the accuracy of a number copied off a web page, and
    this project's character is that each figure it quotes is measured against
    something independent. The photographs carry no GPS either, so the baseline
    between two of them is not available. Revisit only with a distance measured
    on the ground.
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
- [x] **The course's code is not at risk** (2026-09-14). The worry was that
  `../MGRCV-history-backup-2026-09-10.bundle` had become its only copy once
  `legacy/` was deleted. It has not: the original work is in a repository of
  its own. The bundle stays as a convenience, not as a last copy.
