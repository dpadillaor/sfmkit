# Development

## The repository

```
packages/sfmkit/      the library and CLI, in four layers
packages/viewer/      sfmview, in ports and adapters
contracts/            the messages the two exchange, with a schema and examples
configs/<project>/    one YAML per experiment
data/<project>/       the photographs; never written to
runs/<project>/…      outputs, not in version control
examples/             one saved run of each kind, tracked and copied into the images
docs/                 the long-form notes: the old photograph, optimisations, the viewer
website/              this site
tools/                our own scripts: figures, films, experiments. Not installed
```

Each package is installable on its own, with its own `pyproject.toml`,
requirements, `Dockerfile`, `src/` and `tests/`. Commands are run from the
package's directory; the build context of every image is the repository root.

## The checks

Before any commit, from the root:

```bash
ruff check . && (cd packages/sfmkit && lint-imports && pytest -q)
```

and for the viewer, in its own environment:

```bash
make check PKG=viewer
```

`lint-imports` is the layering, enforced rather than described:

| Contract | |
|---|---|
| Layered architecture | `apps → render → data → core`, one direction only |
| The core does no I/O and draws nothing | no matplotlib, torch, yaml or rich in `core` |
| Only the render layer imports matplotlib | |
| Only the data layer imports torch | |

The viewer's own contracts keep the API away from the adapters, and both
packages test against `contracts/step.schema.json`, so a change to the live
message format breaks a test on both sides rather than a run.

## The regression check

The tests need no dataset. The pipeline's behaviour, though, is checked by
re-running the stages on the saved example, whose matches and COLMAP model come
from a CPU:

```bash
mkdir -p /tmp/check/valencia && cp -r examples/valencia/cpu /tmp/check/valencia/
for s in verify reconstruct localize evaluate; do
  SFMKIT_RUNS=/tmp/check sfmkit $s --config configs/valencia/cpu.yaml
done
# 14 cameras, 2850 points, mean rotation error 0.338°, the old photo 1.32°
```

Because its COLMAP model is the example's, the check scores against a fixed
reference: what moves is our code, not COLMAP's randomness.

## Conventions

- **The backlog is `TODO.md`.** Every discovery goes there — a bug, a
  limitation, an idea, a question left open — with a line of context so it
  still makes sense a month later.
- **Documentation is prose.** The long arguments live in `docs/`:
  `old-photo.md` for the photograph the project is about, `optimizations.md`
  for what was measured and what it bought, `viewer.md` for the contract.
- **A result records its commit.** Every stage writes a manifest with the
  commit, the versions and the whole config, so a figure can be traced to the
  code that made it.
- **Figures and films are code.** `tools/` draws every one of them from a run,
  so none of them can drift from the results they illustrate.

## Continuous integration

`.github/workflows/` carries four:

| Workflow | When | What |
|---|---|---|
| **Checks** (`ci.yml`) | main, pull requests | `pip check` on the installed pins, ruff, the import contracts and both test suites, with a Redis service so the broker's own tests run; then the saved example put through `verify`…`evaluate` again, and its numbers checked. A pull request's run is cancelled when it is pushed again; main's never is |
| **Documentation** (`docs.yml`) | main, pull requests touching `website/` | builds this site with `--strict`, and publishes it to GitHub Pages from main |
| **Docker images** (`images.yml`) | main, published releases, or by hand | builds the CPU and viewer images on every change to them; publishes them to the registry when a release is published, tagged with the version, `cpu`/`latest` and the commit. The GPU image is built where there is a GPU: `make push DEVICE=gpu` |
| **Notify** (`notify.yml`) | any of the three finishing | posts a failure to a Discord channel, and nothing when they pass |

Everything they install comes from the same pinned requirements files as the
conda environments, so a green CI means the documented installation works.

Because that installation is `--no-deps`, pip is never asked whether a pinned
version suits the package that needs it, and a wrong pin only shows up as an
import error in the middle of the tests. So each job runs `pip check` straight
after installing: a disagreement is then one line naming both packages. The one
disagreement allowed is lightglue asking for `opencv-python` where
`opencv-python-headless` is installed, which is the same library without the
GUI.

### Where a failure is heard

GitHub's own route is email, and it goes to the same inbox as everything else.
So the email is turned off — <https://github.com/settings/notifications>,
**Actions**, uncheck **Email** (or leave it on and set *Notify for failed
workflows only*) — and `notify.yml` posts failures to a Discord channel
instead, where they can be muted, read late, or left to the phone.

It needs one repository secret:

```bash
# Discord: the channel's Edit Channel -> Integrations -> Webhooks -> New
# Webhook -> Copy Webhook URL. Then, in a clone of this repository:
gh secret set DISCORD_WEBHOOK
```

Without the secret the job says so and passes, so a fork is never failed by a
secret it cannot have. It posts on `failure` only: a green run is not news.
