"""Two photographs of one wall, a century apart, brought together: an animation.

    python tools/changes_animation.py --layout side --format webp

Five movements: the two photographs side by side (or one above the other),
today's growing to fill the frame, the old one flying onto it and deforming
until the homography's four corners meet, the two blended, and the change map
rising where they overlap. The homography and the map are the `changes`
stage's own, computed here from the run's verified matches, so the picture
cannot drift from the results.

Set in the viewer's own IBM Plex Sans, which needs ``brotli`` alongside the
fontTools that comes with matplotlib; without it, matplotlib's DejaVu Sans.

Writes an animated WebP (a fifth of a GIF's weight, and no banding in the
sky), an MP4 for a page that can carry video, a GIF for one that cannot, or
all three.
"""

import argparse
import functools
from io import BytesIO
from pathlib import Path

import cv2
import matplotlib
import numpy as np
from animate import FORMATS, save
from PIL import Image, ImageDraw, ImageFont

from sfmkit.core.changes import detect_changes
from sfmkit.data import io
from sfmkit.data.config import default_run_dir, load_config

ROOT = Path(__file__).resolve().parents[1]
PLEX = ROOT / "packages/viewer/src/sfmview/web/vendor/fonts/ibmplexsans-latin.woff2"
FALLBACK = Path(matplotlib.__file__).parent / "mpl-data/fonts/ttf/DejaVuSans.ttf"
GROUND = (16, 16, 16)  # the viewer's, so the figures of this project match
SIGNAL = (0, 79, 255)  # the viewer's orange, in BGR

# What to point at once the change map is up: the boxes of one remark, in
# fractions of the modern photograph. Hand-placed, and true of Valencia's pair
# alone; the change map under them is the pipeline's own.
PLACES = [
    ([(0.104, 0.300, 0.230, 0.897), (0.433, 0.235, 0.577, 0.908),
      (0.347, 0.648, 0.420, 0.900)],
     "The lamp posts have moved"),
    ([(0.304, 0.400, 0.549, 0.604)], "The gallery now opens onto a courtyard"),
    ([(0.640, 0.528, 0.781, 0.871)], "A building beside the cathedral is gone"),
    ([(0.166, 0.795, 0.231, 0.950), (0.252, 0.790, 0.428, 0.995),
      (0.455, 0.778, 0.616, 0.995), (0.653, 0.781, 0.827, 0.945)],
     "People in both, never in the same place"),
]


@functools.cache
def typeface() -> bytes:
    """The viewer's own IBM Plex Sans, as something PIL can open.

    The viewer keeps it as woff2, which PIL cannot read; fontTools decompresses
    it (through brotli) and writes it back out as TrueType, so the figures and
    the viewer are set in one typeface kept in one place.
    """
    try:
        from fontTools.ttLib import TTFont
        out = BytesIO()
        font = TTFont(PLEX)
        font.flavor = None
        font.save(out)
        return out.getvalue()
    except Exception:  # noqa: BLE001 - any of fontTools, brotli or the file
        return FALLBACK.read_bytes()


def ease(t: float) -> float:
    """Smooth start and stop, so a photograph settles rather than stops."""
    return t * t * (3 - 2 * t)


def corners(w: int, h: int) -> np.ndarray:
    return np.float32([[0, 0], [w, 0], [w, h], [0, h]])


def fitted(shape, box) -> np.ndarray:
    """The corners an image of ``shape`` takes when fitted into ``box``, keeping its shape."""
    x, y, w, h = box
    scale = min(w / shape[1], h / shape[0])
    size = np.float32([shape[1], shape[0]]) * scale
    at = np.float32([x + (w - size[0]) / 2, y + (h - size[1]) / 2])
    return corners(*size) + at


def slots(layout: str, canvas, old_shape, modern_shape, margin=0.05):
    """Where the two photographs wait before they meet: side by side, or stacked.

    Both are drawn the same height (side by side) or the same width (stacked),
    whatever their shapes, so the pair reads as a pair.
    """
    h, w = canvas
    gap, edge = int(margin * w), int(margin * w)
    if layout == "side":
        half, tall = (w - 2 * edge - gap) / 2, h - 2 * edge - h * 0.09  # room for the labels
        size = [(min(half, tall * s[1] / s[0]), min(tall, half * s[0] / s[1]))
                for s in (modern_shape, old_shape)]
        height = min(box[1] for box in size)
        widths = [height * s[1] / s[0] for s in (modern_shape, old_shape)]
        left = (w - sum(widths) - gap) / 2
        boxes = [(left, (h - height) / 2 - h * 0.04, widths[0], height),
                 (left + widths[0] + gap, (h - height) / 2 - h * 0.04, widths[1], height)]
    else:
        half = (h - 2 * edge - gap) / 2 - h * 0.05
        width = min(min(w - 2 * edge, half * s[1] / s[0]) for s in (modern_shape, old_shape))
        heights = [width * s[0] / s[1] for s in (modern_shape, old_shape)]
        top = (h - sum(heights) - gap) / 2 - h * 0.02
        boxes = [((w - width) / 2, top, width, heights[0]),
                 ((w - width) / 2, top + heights[0] + gap, width, heights[1])]
    return fitted(modern_shape, boxes[0]), fitted(old_shape, boxes[1])


def to_draw(photo, widest: float) -> np.ndarray:
    """``photo`` shrunk to the widest it is ever drawn, by area rather than by sampling.

    Warping a 4000 px photograph straight into a 700 px quadrilateral samples
    one pixel in six and throws the rest away, which is what makes the result
    look cheap; scaling it down first averages them instead.
    """
    scale = min(1.0, 1.3 * widest / photo.shape[1])
    if scale >= 1.0:
        return photo
    size = (round(photo.shape[1] * scale), round(photo.shape[0] * scale))
    return cv2.resize(photo, size, interpolation=cv2.INTER_AREA)


def onto(photo, quad, size) -> tuple[np.ndarray, np.ndarray]:
    """``photo`` warped so its corners meet ``quad``, and where it covers."""
    h, w = photo.shape[:2]
    H = cv2.getPerspectiveTransform(corners(w, h), np.float32(quad))
    warped = cv2.warpPerspective(photo, H, size, flags=cv2.INTER_CUBIC)
    covered = cv2.warpPerspective(np.full((h, w), 255, np.uint8), H, size)
    return warped, covered


def draw_on(canvas, photo, quad, alpha: float = 1.0, border: int = 1) -> np.ndarray:
    """``photo`` warped onto ``quad``, over ``canvas`` at ``alpha``."""
    size = (canvas.shape[1], canvas.shape[0])
    warped, covered = onto(photo, quad, size)
    if border:
        cv2.polylines(covered, [np.int32(quad)], True, 255, border)
        cv2.polylines(warped, [np.int32(quad)], True, (255, 255, 255), border)
    mask = (covered.astype(np.float32) / 255 * alpha)[..., None]
    return (canvas * (1 - mask) + warped * mask).astype(np.uint8)


def change_on(canvas, heat, covered, t: float) -> np.ndarray:
    """The change map rising where the two overlap, today's dimmed around it."""
    inside = (covered.astype(np.float32) / 255)[..., None]
    dimmed = canvas * (1 - 0.45 * t * (1 - inside))
    return (dimmed * (1 - t * inside) + heat * (t * inside)).astype(np.uint8)


def within(boxes, shape) -> np.ndarray:
    """A soft mask over ``boxes``, given in fractions of the frame."""
    h, w = shape[:2]
    mask = np.zeros((h, w), np.float32)
    for box in boxes:
        mask[int(box[1] * h):int(box[3] * h), int(box[0] * w):int(box[2] * w)] = 1.0
    return cv2.GaussianBlur(mask, (0, 0), max(1.0, w / 500))[..., None]


def swapped(frame, other, mask, t: float) -> np.ndarray:
    """``other`` showing through ``frame`` inside ``mask``, ``t`` of the way."""
    return (frame * (1 - t * mask) + other * (t * mask)).astype(np.uint8)


def point_at(frame, boxes, text: str, alpha: float = 1.0) -> np.ndarray:
    """Thin frames around ``boxes``, in fractions of the frame, named above the first."""
    h, w = frame.shape[:2]
    drawn = frame.copy()
    for box in boxes:
        corner = (int(box[0] * w), int(box[1] * h))
        cv2.rectangle(drawn, corner, (int(box[2] * w), int(box[3] * h)), SIGNAL, max(1, w // 700))
    frame = (frame * (1 - alpha) + drawn * alpha).astype(np.uint8)
    first = min(boxes, key=lambda b: (b[1], b[0]))
    return label(frame, text, (int(first[0] * w), int(first[1] * h)), alpha)


def label(frame, text: str, at=None, alpha: float = 1.0) -> np.ndarray:
    """``text`` at a corner, under a quadrilateral, or as the title, top left."""
    if not text or alpha <= 0.01:
        return frame
    image = Image.fromarray(frame[..., ::-1])
    draw = ImageDraw.Draw(image, "RGBA")
    size = max(14, image.width // 46)
    font = ImageFont.truetype(BytesIO(typeface()), size)
    box = draw.textbbox((0, 0), text, font=font)
    pad = 8
    title = 26 + size + 2 * pad + 12  # the band the title keeps for itself
    if at is None:  # the title
        x, y = 26, 26
    elif isinstance(at, tuple):  # above a corner, or under it near the top
        x, y = at
        y = y - box[3] - 3 * pad if y > box[3] + 4 * pad else y + 2 * pad
        y = max(y, title)  # never over the title
        x = min(max(x, pad + 4), image.width - box[2] - pad - 4)
    else:  # under a quadrilateral, centred
        x = float(np.mean(at[:, 0])) - box[2] / 2
        y = min(float(np.max(at[:, 1])) + 10, image.height - 12 - box[3])
    plate = 255 if at is None else 210  # the title sits on the ground, solid
    draw.rectangle([x - pad, y - pad, x + box[2] + pad, y + box[3] + pad],
                   fill=(*GROUND[::-1], int(plate * alpha)))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, int(255 * alpha)))
    return np.asarray(image)[..., ::-1]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--config", default="projects/valencia/configs/gpu-dense.yaml")
    p.add_argument("--out", type=Path, default=Path("website/docs/figures/old_photo"))
    p.add_argument("--layout", choices=("side", "stack"), default="side")
    p.add_argument("--format", choices=FORMATS, default="webp")
    p.add_argument("--width", type=int, default=1200)
    p.add_argument("--fps", type=int, default=12)
    p.add_argument("--colours", type=int, default=96, help="the GIF's palette")
    p.add_argument("--quality", type=int, default=78, help="the WebP's, 0 to 100")
    p.add_argument("--crf", type=int, default=23, help="the MP4's, lower is better")
    args = p.parse_args()

    cfg = load_config(args.config)
    run = default_run_dir(cfg)
    query, target = cfg.localize.query, cfg.sfm.reference
    pair = [f for f in (run / "verify").glob("*.npz") if {query, target} == set(f.stem.split("__"))]
    m = io.load_matches(pair[0])
    p0, p1 = m.points()
    src, dst = (p0, p1) if m.image0 == query else (p1, p0)
    old = io.read_image(io.image_file(cfg.scene_dir, query))
    modern = io.read_image(io.image_file(cfg.scene_dir, target))
    change = detect_changes(old, modern, src, dst, seed=cfg.seed)

    scale = args.width / modern.shape[1]
    size = (args.width, round(modern.shape[0] * scale))
    canvas = np.tile(np.uint8(GROUND), (size[1], size[0], 1))
    full = corners(*size)
    heat = cv2.resize(change.matched_difference, size, interpolation=cv2.INTER_AREA)
    landed = np.float32(cv2.perspectiveTransform(
        corners(*old.shape[1::-1])[None], change.homography)[0] * scale)
    modern_slot, old_slot = slots(args.layout, (size[1], size[0]), old.shape, modern.shape)
    # Each is drawn at most as wide as the frame, or as its landed quadrilateral.
    modern = to_draw(modern, size[0])
    old = to_draw(old, max(np.ptp(landed[:, 0]), np.ptp(old_slot[:, 0])))

    frames, times = [], []

    def add(frame, seconds=None):
        frames.append(frame)
        times.append(round(1000 * (seconds if seconds else 1 / args.fps)))

    def hold(seconds):
        times[-1] += round(1000 * seconds)

    def both(modern_quad, old_quad, old_alpha=1.0, names=True):
        frame = draw_on(draw_on(canvas, modern, modern_quad), old, old_quad, old_alpha)
        if names:
            frame = label(frame, f"{target}, today", modern_quad)
            frame = label(frame, f"{query}, undated", old_quad)
        return frame

    add(both(modern_slot, old_slot), 2.2)  # the two of them, side by side
    steps = round(1.6 * args.fps)
    for i in range(steps):  # today's grows to fill the frame
        t = ease((i + 1) / steps)
        add(both(modern_slot * (1 - t) + full * t, old_slot, names=t < 0.5))
    hold(0.5)
    steps = round(2.4 * args.fps)
    for i in range(steps):  # and the old one flies onto it, deforming as it goes
        t = ease((i + 1) / steps)
        add(label(draw_on(draw_on(canvas, modern, full), old, old_slot * (1 - t) + landed * t),
                  f"{query}, placed by its homography" if t > 0.25 else ""))
    hold(1.2)
    steps = round(1.2 * args.fps)
    for i in range(steps):  # it turns transparent over today's
        a = 1 - 0.55 * ease((i + 1) / steps)
        add(label(draw_on(draw_on(canvas, modern, full), old, landed, a),
                  "The same wall, a century apart"))
    hold(1.6)
    blended = draw_on(draw_on(canvas, modern, full), old, landed, 0.45)
    covered = onto(old, landed, size)[1]
    caption = "What changed"
    steps = round(1.0 * args.fps)
    for i in range(steps):  # and what differs rises where they overlap
        t = ease((i + 1) / steps)
        add(label(change_on(blended, heat, covered, t), caption))
    hold(1.4)

    # The changes are named on the comparison itself: it is what they are read
    # off, and moving to another ground would make the viewer place them twice.
    marked = frames[-1].copy()
    then = draw_on(draw_on(canvas, modern, full), old, landed)
    now = draw_on(canvas, modern, full)

    def sweep(base, boxes, text, other, seconds, wait):
        """Inside ``boxes`` alone, ``base`` gives way to ``other`` and holds."""
        steps = round(seconds * args.fps)
        mask = within(boxes, base.shape)
        for i in range(steps):
            add(point_at(swapped(base, other, mask, ease((i + 1) / steps)), boxes, text))
        hold(wait)
        return swapped(base, other, mask, 1.0)

    for boxes, text in PLACES:  # each named, then looked at in both photographs
        steps = round(0.4 * args.fps)
        for i in range(steps):
            add(point_at(marked, boxes, text, ease((i + 1) / steps)))
        hold(1.0)
        seen = sweep(marked, boxes, text, then, 0.6, 1.3)
        seen = sweep(seen, boxes, text, now, 0.6, 1.3)
        sweep(seen, boxes, text, marked, 0.5, 0.8)
        marked = point_at(marked, boxes, text)
    hold(1.6)

    steps = round(0.8 * args.fps)  # and back to the pair, so the loop does not jolt
    opening = both(modern_slot, old_slot)
    for i in range(steps):
        t = ease((i + 1) / steps)
        add((marked * (1 - t) + opening * t).astype(np.uint8))

    save(frames, times, args.out, args.format, fps=args.fps, quality=args.quality,
         colours=args.colours, crf=args.crf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
