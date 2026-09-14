# Working on this repository

## The backlog

`TODO.md` is the list of open work. **Every discovery goes there**: a bug, a
limitation, an idea, a question left open. If it is not fixed on the spot, it
is written down, with one line of context so it makes sense a month later.
Tick or remove an item when it is done. Read it before starting.

## Checks

Two conda environments for sfmkit, built from its requirements files exactly as
the README tells users to, Python 3.11 both: `sfmkit` (CPU,
`requirements-cpu.txt`) and `sfmkit-gpu` (CUDA 12.1, `requirements-gpu.txt`).
Before any commit, from the root:

```bash
ruff check . && (cd packages/sfmkit && lint-imports && pytest -q)
```

The viewer has its own environment, `sfmview` (its requirements only, so an
import of sfmkit would fail), checked the same way from `packages/viewer`, or
`make check PKG=viewer`.

The regression check for anything touching the pipeline reruns our stages on
the project's frozen run, whose matches and COLMAP model came from a CPU:

```bash
cd projects/valencia
cp -r runs/reference-cpu runs/cpu          # cpu.yaml writes `cpu`, so start from the frozen one
for s in verify reconstruct localize evaluate; do
  sfmkit $s --config configs/cpu.yaml
done
# 14 cameras, 2850 points, mean rotation error 0.338°, the old photo 1.32°
```

Its COLMAP model is the frozen run's, so the check scores against a fixed
reference. A full run from scratch on a GPU (`projects/valencia/configs/gpu-dense.yaml`),
whose matches differ, gives 14 cameras, 2830 points, 0.300° and 0.60°; it runs
COLMAP again too, which varies a little between runs, the old photo most.

## Layout

- `packages/<name>/` one installable package each, with its own `pyproject.toml`,
  requirements, `Dockerfile`, `src/` and `tests/`. Tests and the commands are run
  from the package's directory; the build context of every image is the root.
- `packages/viewer/src/sfmview/`, the web viewer, in ports and adapters; it
  reads runs through the contract in `docs/viewer.md` and never imports sfmkit.
- `packages/contracts/` (`sfmcontracts`) the only thing the two share: the
  messages they pass (`step.schema.json`, `asyncapi.yaml`) and the files a run
  leaves behind (`run.schema.json`), with the checkers both suites import. It
  imports nothing but the standard library, enforced by import-linter, so
  being underneath both costs neither a dependency.
- `packages/sfmkit/src/sfmkit/` in four layers, `apps → render → data → core`, enforced by
  import-linter. `core` does no I/O and imports no torch, matplotlib, yaml
  or rich.
- `projects/<name>/` one project, and everything it owns: `data/` (the
  photographs and anything precomputed, never written), `configs/*.yaml` (one
  experiment each), and `runs/<config>/<stage>/` (outputs, ignored by git). The
  project is the directory its config sits in -- nothing names it twice.
- `projects/<name>/runs/reference-*` the frozen runs, tracked and copied into
  the image: what the regression check measures against, and what the viewer
  has to show before you have run anything. Named so that no config can write
  over one, since `cpu.yaml` writes `cpu`.

## Git

- Stage files by name, never `git add -A`: the user edits files at the same time.
- Commit before generating anything that records the commit (a run, an image),
  so the recorded commit names the code that produced it.
- **No co-author trailers, and no mention of the assistant in a commit.** The
  history is the author's, under `181723095+dpadillaor@users.noreply.github.com`;
  the messages say what changed and why, and nothing about what wrote them.
  Decided on 2026-09-13 and applied to the whole history, which was rewritten
  for it.
- Never rewrite history without asking. Two bundles sit beside the repository:
  `../MGRCV-history-backup-2026-09-10.bundle` (the course's code, tag
  `baseline-original`) and `../MGRCV-backup-before-rewrite-2026-09-13.bundle`
  (everything as it stood before that rewrite).
- The repository is public: `github.com/dpadillaor/sfmkit`. Work goes in on a
  branch and a pull request, not straight to `main`, so the checks speak before
  a change lands.

## Working with the user

- Conversation in Spanish; code, comments, commits and docs in English.
- Docker is being learnt step by step: one concept at a time, a fictitious
  example, and the user writes the Dockerfile and compose file.
- Short docstrings, few comments. Ask before installing anything.
