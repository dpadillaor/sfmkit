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

The regression check for anything touching the pipeline starts from the saved
example, whose matches came from a GPU:

```bash
mkdir -p /tmp/check/valencia && cp -r examples/valencia/9cameras /tmp/check/valencia/
SFMKIT_RUNS=/tmp/check sfmkit run --config configs/valencia/9cameras.yaml --from verify
# mean rotation error 0.379°
```

A full run from scratch in `sfmkit-gpu` reproduces the example (9 cameras, 1868
points); on CPU, whose matches differ, it gives 9 cameras, 1857 points and
0.379° too.

## Layout

- `packages/<name>/` one installable package each, with its own `pyproject.toml`,
  requirements, `Dockerfile`, `src/` and `tests/`. Tests and the commands are run
  from the package's directory; the build context of every image is the root.
- `packages/viewer/src/sfmview/`, the web viewer, in ports and adapters; it
  reads runs through the contract in `docs/viewer.md` and never imports sfmkit.
- `contracts/` the messages the packages exchange (`step.schema.json`, live
  progress through Redis), with examples and the checker both test suites load.
- `packages/sfmkit/src/sfmkit/` in four layers, `apps → render → data → core`, enforced by
  import-linter. `core` does no I/O and imports no torch, matplotlib, yaml, rich
  or textual.
- `data/<project>/` raw inputs, never written. `configs/<project>/*.yaml` one
  experiment each. `runs/<project>/<config>/<stage>/` outputs, ignored by git.
- `examples/` a saved run, tracked and copied into the image.
- `legacy/` the original course code, ignored by git, kept on disk for reference.

## Git

- Stage files by name, never `git add -A`: the user edits files at the same time.
- Commit before generating anything that records the commit (a run, an image),
  so the recorded commit names the code that produced it.
- Never delete `legacy/` or rewrite history without asking.

## Working with the user

- Conversation in Spanish; code, comments, commits and docs in English.
- Docker is being learnt step by step: one concept at a time, a fictitious
  example, and the user writes the Dockerfile and compose file.
- Short docstrings, few comments. Ask before installing anything.
