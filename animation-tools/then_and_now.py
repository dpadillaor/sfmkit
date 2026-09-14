"""The README's opening figure: everything the project was given.

The undated photograph beside the one it is matched against, large enough to be
compared, and the rest of the set underneath at a size that says how many there
are rather than what is in them. Which photographs these are comes out of the
config, so the figure cannot drift from the experiment it illustrates.

    python animation-tools/then_and_now.py
"""

import argparse
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from animate import GROUND, typeface
from PIL import Image, ImageDraw, ImageFont

from sfmkit.core.orientation import upright
from sfmkit.data.config import load_config
from sfmkit.data.exif import read_orientation
from sfmkit.data.io import image_file, read_image

HEIGHT, GAP, STRIP_GAP, PAD = 400, 10, 6, 22


def at_height(image: np.ndarray, height: int) -> np.ndarray:
    width = round(image.shape[1] * height / image.shape[0])
    return cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)


def caption(frame: np.ndarray, text: str, size: int) -> np.ndarray:
    """A plate in the top-left corner, lettered like every other figure here."""
    image = Image.fromarray(frame[..., ::-1])
    draw = ImageDraw.Draw(image, "RGBA")
    font = ImageFont.truetype(BytesIO(typeface()), size)
    box = draw.textbbox((0, 0), text, font=font)
    pad = 9
    draw.rectangle([PAD - pad, PAD - pad, PAD + box[2] + pad, PAD + box[3] + pad],
                   fill=(*GROUND[::-1], 225))
    draw.text((PAD, PAD), text, font=font, fill=(255, 255, 255, 255))
    return np.asarray(image)[..., ::-1]


def row(images: list[np.ndarray], gap: int, width: int | None = None) -> np.ndarray:
    """Images side by side on white, brought to ``width`` if one is given.

    Rounding each thumbnail to whole pixels leaves the row a pixel or two off
    whatever it was sized for, which is a pixel or two of white, or of nothing.
    """
    height = images[0].shape[0]
    spacer = np.full((height, gap, 3), 255, np.uint8)
    strip = np.hstack([x for pair in zip(images, [spacer] * len(images), strict=True)
                       for x in pair][:-1])
    if width and strip.shape[1] < width:
        strip = np.hstack([strip, np.full((height, width - strip.shape[1], 3), 255, np.uint8)])
    return strip[:, :width] if width else strip


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--config", default="projects/valencia/configs/cpu.yaml")
    p.add_argument("--out", type=Path, default=Path("website/docs/figures/then_and_now.jpg"))
    args = p.parse_args()

    cfg = load_config(args.config)
    scene = cfg.scene_dir
    reference = cfg.sfm.reference or cfg.sfm.images[0]
    query = cfg.localize.query
    others = [n for n in cfg.sfm.images if n != reference]

    def load(name):
        """As the photograph is meant to be seen: a phone stores some of these
        on their side and says so in EXIF, which is why the pipeline turns them
        too before it looks for features."""
        path = image_file(scene, name)
        return at_height(upright(read_image(path), read_orientation(path)), HEIGHT)

    # One size for both plates: sized off each photograph's own width, the two
    # labels come out different, which reads as a mistake.
    old, ref = load(query), load(reference)
    size = max(15, min(old.shape[1], ref.shape[1]) // 30)
    top = row([caption(old, f"{query} · undated, camera unknown", size),
               caption(ref, f"{reference} · the reference", size)], GAP)

    # The strip is sized to end where the two photographs above it end, so its
    # height is whatever the number of them leaves over rather than a choice.
    rest = [load(n) for n in others]
    aspects = [i.shape[1] / i.shape[0] for i in rest]
    height = round((top.shape[1] - STRIP_GAP * (len(rest) - 1)) / sum(aspects))
    strip = row([at_height(i, height) for i in rest], STRIP_GAP, width=top.shape[1])

    figure = np.vstack([top, np.full((GAP, top.shape[1], 3), 255, np.uint8), strip])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.out), figure, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"{args.out}: {figure.shape[1]}x{figure.shape[0]}, "
          f"{len(others)} more at {height} px, {args.out.stat().st_size / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
