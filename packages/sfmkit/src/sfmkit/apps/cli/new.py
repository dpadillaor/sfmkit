"""The `sfmkit new` command."""

from __future__ import annotations

import shutil
import textwrap
from collections import Counter
from pathlib import Path

from sfmkit.apps.cli._common import console
from sfmkit.data.config import load_config

IMAGES = (".jpg", ".jpeg", ".png", ".tif", ".tiff")

TEMPLATE = """\
# Every stage on the CPU alone, so any machine reproduces it. Paths are
# relative to the project's data/.
seed: 0

calibrate:
  exif: true                # the focal length recorded in the photographs
  sensor_aspect: [4, 3]     # the whole sensor, which a 16:9 photograph is a cut of
  # instead of the EXIF: a 3x3 K you already have, or photographs of a chessboard
  # intrinsics: K.txt
  # images: chessboard/*.jpg

sfm:
{images}
  # reference: Img01        # what everything is anchored to; the first, by default
  exhaustive: true          # every pair, not only those touching the reference
  max_keypoints: 2048
  device: auto              # auto | cpu | cuda: the last two give different matches
  min_triangulation_angle_deg: 2.0
  max_reprojection_error: 12.0
  pnp_threshold: 6.0

# A stage this config says nothing about is one `sfmkit run` walks past.

# localize:
#   query: Img_Old          # a photograph to place, kept out of the reconstruction

# colmap:
#   matches: colmap         # what the run is scored against; needs COLMAP installed

dense:
  enabled: false            # COLMAP's dense cloud of the scene; needs CUDA
"""


def cmd_new(args) -> int:
    """Lay out a project: data/, configs/, and a config that parses."""
    project = Path(args.inside) / args.name
    if project.exists():
        console.print(f"[red]{project} already exists[/red]")
        return 1

    photographs: list[Path] = []
    if args.photos:
        photographs = _photographs(args.photos)
        if not photographs:
            console.print(f"[red]no photographs in {args.photos}[/red]")
            return 1
        clash = [n for n, count in Counter(p.stem for p in photographs).items() if count > 1]
        if clash:
            console.print(f"[red]two photographs share a name:[/red] {', '.join(clash)}")
            return 1

    scene = project / "data" / "scene"
    scene.mkdir(parents=True)
    (project / "configs").mkdir()
    for photograph in photographs:
        shutil.copyfile(photograph, scene / photograph.name)

    names = [p.stem for p in photographs]
    config = project / "configs" / "cpu.yaml"
    config.write_text(TEMPLATE.format(images=_images(names)))
    load_config(config)  # what was written is a config, not a piece of text

    if names:
        console.print(f"copied {len(names)} photographs into {scene}")
    console.print(f"[green]{project}[/green]")
    for line in _next_steps(project, config, names):
        console.print(f"  {line}")
    return 0


def _photographs(source) -> list[Path]:
    return sorted(p for p in Path(source).iterdir() if p.suffix.lower() in IMAGES)


def _images(names: list[str]) -> str:
    """The ``images`` key, wrapped the way a hand would wrap it."""
    if not names:
        return "  images: []                # the photographs, by name without extension"
    return textwrap.fill(f"images: [{', '.join(names)}]", width=96,
                         initial_indent="  ", subsequent_indent="           ")


def _next_steps(project: Path, config: Path, names: list[str]) -> list[str]:
    """A project without photographs cannot run yet, and says what it wants."""
    if names:
        return [f"sfmkit run --config {config}"]
    return [f"put the photographs in {project / 'data' / 'scene'}",
            f"list them under `sfm.images` in {config}",
            f"then: sfmkit run --config {config}"]
