"""The figure for live progress: one run being watched while it is made.

Cut from a screen recording of the viewer beside the console that is driving
it, which is the only way to show the thing the live path is for: the two
halves agreeing, a stage at a time, with nobody reloading anything.

    python animation-tools/live_film.py --source ~/live-raw.mkv

One shot, not five, because what it shows is continuous. The titles are timed
against the recording itself rather than against the cut, so moving the window
does not move them: the first is up while `verify` is
still counting RANSAC down the right-hand side, and the next one arrives
exactly when `reconstruct` starts.
"""

import argparse
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from animate import typeface
from PIL import Image, ImageDraw, ImageFont
from viewer_film import AMBER, every, joined, shot, write

# Seconds of the recording. `verify` starts at 79 and its RANSAC counts up the
# right-hand pane until 83, when `reconstruct` takes over and the first cameras
# appear; 14 of them are in by 92. Ending there is the point: the film is over
# when the reconstruction is.
WINDOW = (78.5, 94.0)
SPEED = 1.0

# (from, to, eyebrow, title) in those same seconds. The first names what is
# being looked at while `verify` counts RANSAC up the right-hand pane; the
# second arrives with `reconstruct`, on the frame the first camera appears, and
# stays: the figure loops, and a title that leaves halfway leaves most of the
# loop unlabelled.
TITLES = [
    (78.5, 82.4, "LIVE", "A run drawn while it is being made"),
    (82.8, 94.0, "RECONSTRUCT", "Each camera as it is registered"),
]

# Top-left of the viewer's canvas, in a 1920-wide frame: past the sidebar,
# which ends near 295, and not on the right, where the console is.
ANCHOR = (322, 62)


def _fade(now: float, start: float, end: float, ramp: float = 0.4) -> float:
    """1.0 between ``start`` and ``end``, ramped at both ends, 0 outside."""
    if now < start - ramp or now > end + ramp:
        return 0.0
    return max(0.0, min(1.0, (now - start + ramp) / ramp, (end + ramp - now) / ramp))


def _plex(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(BytesIO(typeface()), size)


def _mono(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(BytesIO(typeface(mono=True)), size)


def title(draw: ImageDraw.ImageDraw, eyebrow: str, text: str, scale: float,
          alpha: float) -> None:
    """The setting the other film uses, anchored left instead of right.

    Right is where the console is, and a title over a scrolling table is a
    title nobody reads. The canvas beside the sidebar is empty until the first
    points arrive, which is exactly when the second title has already gone.
    """
    small, large = _mono(max(9, round(13 * scale))), _plex(max(15, round(25 * scale)))
    track = 2.2 * scale
    left, top = np.array(ANCHOR) * scale
    gap = round(16 * scale)
    draw.rectangle([left, top - 2 * scale, left + 3 * scale, top + 56 * scale],
                   fill=(*AMBER, int(255 * alpha)))
    x = left + gap
    for character in eyebrow:
        draw.text((x, top), character, font=small, fill=(*AMBER, int(255 * alpha)))
        x += draw.textlength(character, font=small) + track
    draw.text((left + gap, top + 24 * scale), text, font=large,
              fill=(255, 255, 255, int(255 * alpha)))


def annotated(frames: list[np.ndarray], fps: int) -> list[np.ndarray]:
    """Each frame titled according to where in the recording it came from."""
    out = []
    for i, frame in enumerate(frames):
        now = WINDOW[0] + i * SPEED / fps
        showing = [(t, _fade(now, t[0], t[1])) for t in TITLES]
        showing = [(t, a) for t, a in showing if a > 0.01]
        if not showing:
            out.append(frame)
            continue
        scale = frame.shape[1] / 1920
        image = Image.fromarray(frame[..., ::-1])
        draw = ImageDraw.Draw(image, "RGBA")
        for (_, _, eyebrow, text), alpha in showing:
            title(draw, eyebrow, text, scale, alpha)
        out.append(np.asarray(image)[..., ::-1])
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source", type=Path, required=True, help="the screen recording")
    p.add_argument("--out", type=Path, default=Path("website/docs/figures/live_film"))
    p.add_argument("--width", type=int, default=1400)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--crf", type=int, default=18)
    p.add_argument("--webp-width", type=int, default=1100)
    p.add_argument("--webp-fps", type=int, default=12)
    p.add_argument("--quality", type=int, default=44, help="the WebP's, 0 to 100")
    args = p.parse_args()

    capture = cv2.VideoCapture(str(args.source))
    if not capture.isOpened():
        raise SystemExit(f"could not open {args.source}")
    frames = shot(capture, *WINDOW, SPEED, args.width, args.fps)
    capture.release()
    if not frames:
        raise SystemExit(f"no frames between {WINDOW[0]} and {WINDOW[1]}")

    film = joined([annotated(frames, args.fps)], args.fps)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    seconds = len(film) / args.fps

    mp4 = args.out.with_suffix(".mp4")
    write(film, mp4, args.fps,
          ["-c:v", "libx264", "-crf", str(args.crf), "-preset", "slow",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart"])
    print(f"{mp4}: {len(film)} frames, {seconds:.1f} s, "
          f"{mp4.stat().st_size / 1e6:.2f} MB")

    webp = args.out.with_suffix(".webp")
    write(every(film, args.fps, args.webp_fps), webp, args.webp_fps,
          ["-c:v", "libwebp_anim", "-lossless", "0", "-q:v", str(args.quality),
           "-loop", "0"], width=args.webp_width)
    print(f"{webp}: {seconds:.1f} s at {args.webp_fps} fps, "
          f"{args.webp_width} px, {webp.stat().st_size / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
