"""A static copy of the viewer: the page, and the API's answers saved as files.

    sfmview-export --projects projects --steps website/demo/steps --out website/site/demo

What it writes needs no server, broker or network, and every path in it is
relative, so it can be published in any folder of any static host and carried
anywhere in an iframe. The page finds its answers through a ``<meta
name="sfmview-data">``; the photos are made smaller, and keep nothing of their
EXIF but the orientation the page reads; a run's live progress is a stream
recorded by ``animation-tools/record_steps.py``, replayed so its timeline rewinds.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from sfmcontracts import step_errors
from sfmview.adapters.images_fs import FsImageStore
from sfmview.adapters.runs_fs import FsRunStore
from sfmview.api.app import WEB
from sfmview.api.schemas import RunOut, SceneOut
from sfmview.domain import ImageNotFound

DATA = "data/"
ORIENTATION = 0x0112


def export(projects, out, *, runs: list[str] | None = None, steps=None,
           photo_size: int = 2048, quality: int = 85) -> dict[str, int]:
    """Write the static copy into ``out``; the bytes of each file, by path."""
    out = Path(out)
    store, images = FsRunStore(projects), FsImageStore(projects)
    summaries = [s for s in store.runs() if runs is None or str(s.run) in runs]
    missing = set(runs or ()) - {str(s.run) for s in summaries}
    if missing:
        raise SystemExit(f"no such run: {', '.join(sorted(missing))}")

    _empty(out)
    shutil.copytree(WEB, out)
    page = out / "index.html"
    page.write_text(page.read_text().replace(
        "<title>", f'<meta name="sfmview-data" content="{DATA}">\n  <title>', 1))
    # Nothing is at work on a copy: false, rather than unknown, says so.
    _write_json(out / DATA / "runs.json", [RunOut.of(s, False).model_dump() for s in summaries])

    photos: dict[str, set[str]] = {}
    for summary in summaries:
        run = summary.run
        here = f"{DATA}runs/{run.project}/{run.config}"
        (out / here).mkdir(parents=True, exist_ok=True)
        scene = store.scene(run)
        body = SceneOut.of(scene)
        if body.dense is not None:
            shutil.copyfile(store.dense_file(run), out / here / "dense.ply")
            body.dense.url = f"{here}/dense.ply"
        if scene.dataset is not None:
            body.images = f"{DATA}images/{scene.dataset}"
            photos.setdefault(scene.dataset, set()).update(
                c.name for m in scene.models for c in m.cameras)
        _write_json(out / here / "scene.json", body.model_dump())
        recorded = Path(steps) / run.project / f"{run.config}.json" if steps else None
        if recorded and recorded.is_file():
            _write_json(out / here / "steps.json", _stream(recorded))

    for dataset, names in photos.items():
        for name in sorted(names):
            try:
                source = images.image_file(dataset, name)
            except ImageNotFound:
                print(f"no photo of {dataset}/{name}: it will have none in the copy")
                continue
            _photo(source, out / DATA / "images" / dataset / f"{name}.jpg", photo_size, quality)

    return {str(p.relative_to(out)): p.stat().st_size for p in sorted(out.rglob("*"))
            if p.is_file()}


def _stream(path: Path) -> list[dict]:
    """A recorded stream as the live socket sends it, ids and all."""
    messages = json.loads(path.read_text())
    for i, message in enumerate(messages):
        if problems := step_errors(message):
            raise SystemExit(f"{path}, message {i}: {problems[0]}")
    return [{"id": f"{i}-0", "message": m} for i, m in enumerate(messages, start=1)]


def _photo(source: Path, target: Path, size: int, quality: int) -> None:
    """``source`` no larger than ``size`` on its long side, as a JPEG whose only
    metadata is its orientation: no GPS, no camera, no date."""
    from PIL import Image  # only an export needs it, not the server

    with Image.open(source) as im:
        orientation = im.getexif().get(ORIENTATION)
        im.thumbnail((size, size), Image.Resampling.LANCZOS)  # never enlarges
        exif = Image.Exif()
        if orientation:
            exif[ORIENTATION] = orientation
        target.parent.mkdir(parents=True, exist_ok=True)
        im.convert("RGB").save(target, "JPEG", quality=quality, optimize=True,
                               progressive=True, exif=exif.tobytes())


def _empty(out: Path) -> None:
    """Make ``out`` an empty directory, if it is empty already or an old copy."""
    if out.exists():
        if any(out.iterdir()) and not (out / DATA / "runs.json").is_file():
            raise SystemExit(f"{out} is not empty and is not a copy of the viewer")
        shutil.rmtree(out)


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False, separators=(",", ":")))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="sfmview-export", description=__doc__.splitlines()[0])
    p.add_argument("--projects", default="projects", help="sfmkit's projects directory")
    p.add_argument("--out", type=Path, required=True, help="where the copy goes")
    p.add_argument("--run", dest="runs", action="append",
                   help="<project>/<config> to include; again for more (default all)")
    p.add_argument("--steps", type=Path,
                   help="recorded streams, <steps>/<project>/<config>.json")
    p.add_argument("--photo-size", type=int, default=2048, help="the long side, in pixels")
    p.add_argument("--quality", type=int, default=85, help="the photos' JPEG quality")
    args = p.parse_args(argv)
    sizes = export(args.projects, args.out, runs=args.runs, steps=args.steps,
                   photo_size=args.photo_size, quality=args.quality)
    data = {k: v for k, v in sizes.items() if k.startswith(DATA)}
    print(f"{args.out}: {len(sizes)} files, {sum(sizes.values()) / 1e6:.1f} MB, "
          f"of which data {sum(data.values()) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
