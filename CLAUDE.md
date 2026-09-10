# Working on this repository

## The backlog

`TODO.md` is the list of open work. **Every discovery goes there**: a bug, a
limitation, an idea, a question left open. If it is not fixed on the spot, it
is written down, with one line of context so it makes sense a month later.
Tick or remove an item when it is done. Read it before starting.

## Checks

The conda environment is `sfmkit`: Python 3.11, CPU only, built from the
requirements files exactly as the README tells users to. Before any commit:

```bash
ruff check . && lint-imports && pytest -q
```

The regression check for anything touching the pipeline starts from the saved
example, whose matches came from a GPU:

```bash
mkdir -p /tmp/check/valencia && cp -r examples/valencia/9cameras /tmp/check/valencia/
SFMKIT_RUNS=/tmp/check sfmkit run --config configs/valencia/9cameras.yaml --from verify
# mean rotation error 0.981°
```

A full run from scratch on CPU gives 1.574° with 8 cameras: CPU matches differ.

## Layout

- `src/sfmkit/` in four layers, `apps → render → data → core`, enforced by
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
