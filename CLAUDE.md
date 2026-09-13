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
the saved example, whose matches and COLMAP model came from a CPU:

```bash
mkdir -p /tmp/check/valencia && cp -r examples/valencia/cpu /tmp/check/valencia/
for s in verify reconstruct localize evaluate; do
  SFMKIT_RUNS=/tmp/check sfmkit $s --config configs/valencia/cpu.yaml
done
# 14 cameras, 2850 points, mean rotation error 0.338°, the old photo 1.32°
```

Its COLMAP model is the example's, so the check scores against a fixed
reference. A full run from scratch on a GPU (`configs/valencia/gpu-dense.yaml`),
whose matches differ, gives 14 cameras, 2830 points, 0.300° and 0.60°; it runs
COLMAP again too, which varies a little between runs, the old photo most.

## Layout

- `packages/<name>/` one installable package each, with its own `pyproject.toml`,
  requirements, `Dockerfile`, `src/` and `tests/`. Tests and the commands are run
  from the package's directory; the build context of every image is the root.
- `packages/viewer/src/sfmview/`, the web viewer, in ports and adapters; it
  reads runs through the contract in `docs/viewer.md` and never imports sfmkit.
- `contracts/` the messages the packages exchange (`step.schema.json`, live
  progress through Redis), with examples and the checker both test suites load.
- `packages/sfmkit/src/sfmkit/` in four layers, `apps → render → data → core`, enforced by
  import-linter. `core` does no I/O and imports no torch, matplotlib, yaml
  or rich.
- `data/<project>/` raw inputs, never written. `configs/<project>/*.yaml` one
  experiment each. `runs/<project>/<config>/<stage>/` outputs, ignored by git.
- `examples/` a saved run, tracked and copied into the image.

## Git

- Stage files by name, never `git add -A`: the user edits files at the same time.
- Commit before generating anything that records the commit (a run, an image),
  so the recorded commit names the code that produced it.
- Never rewrite history without asking. The course's code is no longer on disk:
  it lives in `../MGRCV-history-backup-2026-09-10.bundle`, tag `baseline-original`.

## Working with the user

- Conversation in Spanish; code, comments, commits and docs in English.
- Docker is being learnt step by step: one concept at a time, a fictitious
  example, and the user writes the Dockerfile and compose file.
- Short docstrings, few comments. Ask before installing anything.
