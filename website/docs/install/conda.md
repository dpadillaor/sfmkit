# Install with conda

Everything here is run from the repository root, on Python 3.11. There are
three environments because there are three sets of dependencies, and mixing
them is what the layering forbids:

| Environment | For | Requirements |
|---|---|---|
| `sfmkit` | the library and CLI, CPU only | `packages/sfmkit/requirements-cpu.txt` |
| `sfmkit-gpu` | the same, with CUDA 12.1 PyTorch | `packages/sfmkit/requirements-gpu.txt` |
| `sfmview` | the web viewer | `packages/viewer/requirements.txt` |

Every requirements file is fully pinned and installed with `--no-deps`: the
list is the environment, not a starting point for a resolver. That is why the
same files build the conda environments and the images.

## Get the code

```bash
git clone <repository> sfmkit
cd sfmkit
```

## The library and CLI

=== "CPU"

    ```bash
    conda create -n sfmkit python=3.11 -y
    conda activate sfmkit
    pip install --no-deps -r packages/sfmkit/requirements-cpu.txt
    pip install --no-deps -e packages/contracts -e packages/sfmkit
    ```

=== "GPU (CUDA 12.1)"

    ```bash
    conda create -n sfmkit-gpu python=3.11 -y
    conda activate sfmkit-gpu
    pip install --no-deps -r packages/sfmkit/requirements-gpu.txt
    pip install --no-deps -e packages/contracts -e packages/sfmkit
    ```

Only `match` uses the GPU, and it is about ten times faster there; everything
after it is numpy and runs the same either way. The two give slightly different
matches, so a CPU run and a GPU run of the same config differ a little — that
is expected, and both are checked.

Check the installation, no dataset needed:

```bash
cd packages/sfmkit && pytest -q     # 215 passed, 3 skipped
sfmkit run --help                   # the stages, in the order `run` does them
```

## The viewer

Its own environment, its requirements only. An `import sfmkit` fails in here,
and that is deliberate: the viewer reads runs through a contract, never through
sfmkit's code.

```bash
conda create -n sfmview python=3.11 -y
conda activate sfmview
pip install --no-deps -r packages/viewer/requirements.txt
pip install --no-deps -e packages/contracts -e packages/viewer
sfmview --projects projects                 # http://127.0.0.1:8000
```

## COLMAP

The `colmap` and `dense` stages call [COLMAP](https://colmap.github.io/)
through `pycolmap`, which the requirements install. COLMAP is what the
reconstruction is scored against, so nothing about sfmkit's own answer depends
on it; `dense` additionally needs an NVIDIA GPU.

**Without COLMAP, or without the patience:** the repository carries a COLMAP
model of the same fifteen photographs, and a config that copies it instead of
computing it.

```bash
sfmkit run --config projects/valencia/configs/no-colmap.yaml
```

## The feature weights

`match` uses SuperPoint and LightGlue, whose weights (53 MB) are downloaded on
first use into PyTorch's cache (`$TORCH_HOME`, by default `~/.cache/torch`).
They are not redistributed here: SuperPoint's are Magic Leap's, released for
non-commercial research, so whoever downloads them takes those terms on
themselves.

Offline, sfmkit says exactly which files it wants and where to put them rather
than failing on a socket error.

## Documentation, locally

```bash
conda create -n sfmdocs python=3.11 -y
conda activate sfmdocs
pip install --no-deps -r website/requirements.txt
mkdocs serve -f website/mkdocs.yml  # http://127.0.0.1:8000
```

## Where things live

| Environment variable | Default | What it moves |
|---|---|---|
| `SFMKIT_BROKER` | — | Redis URL to publish live progress to |
| `TORCH_HOME` | `~/.cache/torch` | where the feature weights are cached |
| `SFMVIEW_PROJECTS` | `projects` | the projects directory the viewer reads |
| `SFMVIEW_BROKER` | — | Redis URL the viewer reads live progress from |

A project is one directory and holds everything of its own:

```
projects/valencia/
├── data/      scene/*.jpg, and anything precomputed
├── configs/   one YAML an experiment
└── runs/      <config>/<stage>/, what a run writes
```

The config's own location says which project it belongs to, so nothing names it
twice. Nothing is ever written back into `data/`, which CI checks by
fingerprinting it around a run.
