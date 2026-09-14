"""The README's film of the viewer, cut from a screen recording.

Unlike every other figure here, this one is not drawn from a run: it is a
recording of a person using `sfmview`, because what it has to show is the
using. The recording is not in the repository; it is made by hand, once, and
this script only cuts it. What it does own is the cut: which seconds, how fast,
and what each shot is called.

    python animation-tools/viewer_film.py --source ~/viewer-raw.mkv

Every shot names the claim it backs, so the film and the README paragraph
cannot drift apart. Change one, change the other.
"""

import argparse
import subprocess
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from animate import typeface
from PIL import Image, ImageDraw, ImageFont

# (from, to, how much faster than life, the eyebrow, the title). The seconds
# are of the recording, found by watching it; the speed is per shot because a
# slow orbit and a slider being dragged do not want the same pace.
SHOTS = [
    (1.0, 9.0, 1.3, "01 \u00b7 THE MODEL", "Our reconstruction, and its cameras"),
    (13.5, 24.0, 1.3, "02 \u00b7 DENSE", "COLMAP's dense cloud behind it"),
    (25.0, 38.0, 1.3, "03 \u00b7 A CAMERA", "The photograph, faded over the points"),
    (59.0, 74.0, 1.3, "04 \u00b7 BOTH MODELS", "One frame, one scale"),
    (90.5, 102.0, 1.3, "05 \u00b7 THE OLD PHOTOGRAPH", "Placed against the finished model"),
]

AMBER = (242, 169, 59)  # the viewer's own, and the accent bar of every diagram here

FADE = 0.45  # seconds a title takes to arrive, and to leave
BLEND = 0.3  # seconds of crossfade between two shots


def titled(frame: np.ndarray, eyebrow: str, title: str, alpha: float) -> np.ndarray:
    """The shot's name in the top-right corner, set as the diagrams are.

    A numbered eyebrow in Roboto Mono over the title in IBM Plex Sans, behind an
    amber rule: the same accent the cards of `pipeline.svg` carry. No plate. The
    top of the frame is darkened by a gradient instead, so white letters stay
    legible over pale stone without a rectangle announcing itself.
    """
    if alpha <= 0.01:
        return frame
    scale = frame.shape[1] / 1400
    body = np.asarray(Image.fromarray(frame[..., ::-1])).astype(np.float32)
    band = round(150 * scale)
    ramp = np.clip(np.linspace(1, 0, band) * 0.75 * alpha, 0, 1)[:, None, None]
    body[:band] *= (1 - ramp)

    image = Image.fromarray(body.astype(np.uint8))
    draw = ImageDraw.Draw(image, "RGBA")
    small = ImageFont.truetype(BytesIO(typeface(mono=True)), max(9, round(13 * scale)))
    large = ImageFont.truetype(BytesIO(typeface()), max(15, round(25 * scale)))
    track = 2.2 * scale

    def letter(x, y, text, font, fill):
        """Letter by letter, since PIL has no letter-spacing of its own."""
        for character in text:
            draw.text((x, y), character, font=font, fill=fill)
            x += draw.textlength(character, font=font) + track

    spaced = sum(draw.textlength(c, font=small) + track for c in eyebrow) - track
    margin, gap = round(30 * scale), round(16 * scale)
    left = image.width - margin - max(spaced, draw.textlength(title, font=large)) - gap
    draw.rectangle([left, margin - 2 * scale, left + 3 * scale, margin + 56 * scale],
                   fill=(*AMBER, int(255 * alpha)))
    letter(left + gap, margin, eyebrow, small, (*AMBER, int(255 * alpha)))
    draw.text((left + gap, margin + 24 * scale), title, font=large,
              fill=(255, 255, 255, int(255 * alpha)))
    return np.asarray(image)[..., ::-1]


def shot(capture, start: float, end: float, speed: float, width: int,
         fps: int) -> list[np.ndarray]:
    """The frames of one shot, resampled to ``fps`` at ``speed``, scaled to ``width``.

    Read forwards from one seek rather than seeking per frame: seeking into
    H.264 costs a decode back to the last keyframe every time.
    """
    source_fps = capture.get(cv2.CAP_PROP_FPS)
    wanted = [start + i * speed / fps for i in range(int((end - start) * fps / speed))]
    indices = [round(t * source_fps) for t in wanted]
    capture.set(cv2.CAP_PROP_POS_FRAMES, indices[0])

    frames, at = [], indices[0]
    for index in indices:
        while at <= index:
            ok, raw = capture.read()
            if not ok:
                return frames
            at += 1
        height = round(raw.shape[0] * width / raw.shape[1])
        frames.append(cv2.resize(raw, (width, height), interpolation=cv2.INTER_AREA))
    return frames


def lettered(frames: list[np.ndarray], eyebrow: str, title: str,
             fps: int) -> list[np.ndarray]:
    """The title faded in at the head of the shot and out at its tail."""
    ramp = max(1, round(FADE * fps))
    out = []
    for i, frame in enumerate(frames):
        alpha = min(1.0, (i + 1) / ramp, (len(frames) - i) / ramp)
        out.append(titled(frame, eyebrow, title, alpha))
    return out


def joined(shots: list[list[np.ndarray]], fps: int) -> list[np.ndarray]:
    """The shots end to end, each pair crossfaded so the layers do not jump."""
    n = max(1, round(BLEND * fps))
    film = list(shots[0])
    for nxt in shots[1:]:
        k = min(n, len(film), len(nxt))
        tail, head = film[-k:], nxt[:k]
        film = film[:-k]
        for i, (a, b) in enumerate(zip(tail, head, strict=True)):
            w = (i + 1) / (k + 1)
            film.append(cv2.addWeighted(a, 1 - w, b, w, 0))
        film.extend(nxt[k:])
    return film


def write(frames: list[np.ndarray], out: Path, fps: int, encoder: list[str],
          width: int | None = None) -> None:
    """The film streamed into ffmpeg, so it is never in memory twice.

    ``width`` rescales on the way past, which is how the WebP comes out smaller
    than the MP4 from the same frames rather than from the MP4 itself: a second
    generation of a point cloud is a second generation of noise.
    """
    first = frames[0] if width is None else _at(frames[0], width)
    height, across = (n - n % 2 for n in first.shape[:2])
    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{across}x{height}", "-r", str(fps), "-i", "-", *encoder, str(out)],
        stdin=subprocess.PIPE)
    for frame in frames:
        if width is not None:
            frame = _at(frame, width)
        ffmpeg.stdin.write(np.ascontiguousarray(frame[:height, :across]).tobytes())
    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        raise SystemExit("ffmpeg failed")


def _at(frame: np.ndarray, width: int) -> np.ndarray:
    if frame.shape[1] == width:
        return frame
    height = round(frame.shape[0] * width / frame.shape[1])
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)


def every(frames: list[np.ndarray], fps: int, wanted: int) -> list[np.ndarray]:
    """``frames`` thinned to ``wanted`` frames a second, for the WebP."""
    step = fps / wanted
    return [frames[round(i * step)] for i in range(int(len(frames) / step))]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source", type=Path, required=True, help="the screen recording")
    p.add_argument("--out", type=Path, default=Path("website/docs/figures/viewer_film"))
    p.add_argument("--width", type=int, default=1200)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--crf", type=int, default=18)
    p.add_argument("--webp-width", type=int, default=1000)
    p.add_argument("--webp-fps", type=int, default=12)
    p.add_argument("--quality", type=int, default=42, help="the WebP's, 0 to 100")
    args = p.parse_args()

    capture = cv2.VideoCapture(str(args.source))
    if not capture.isOpened():
        raise SystemExit(f"could not open {args.source}")
    shots = []
    for start, end, speed, eyebrow, title in SHOTS:
        frames = shot(capture, start, end, speed, args.width, args.fps)
        if not frames:
            raise SystemExit(f"no frames between {start} and {end}")
        shots.append(lettered(frames, eyebrow, title, args.fps))
        print(f"  {start:6.1f} to {end:6.1f} at {speed}x: {len(frames):4d} frames, "
              f"{eyebrow}  {title}")
    capture.release()

    film = joined(shots, args.fps)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    seconds = len(film) / args.fps

    mp4 = args.out.with_suffix(".mp4")
    write(film, mp4, args.fps,
          ["-c:v", "libx264", "-crf", str(args.crf), "-preset", "slow",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart"])
    print(f"{mp4}: {len(film)} frames, {seconds:.1f} s, "
          f"{mp4.stat().st_size / 1e6:.2f} MB")

    # The README needs WebP: GitHub animates one in place and leaves a relative
    # .mp4 as a link. Fewer frames a second, because a point cloud is the worst
    # thing a codec can be given and every frame of it costs.
    webp = args.out.with_suffix(".webp")
    write(every(film, args.fps, args.webp_fps), webp, args.webp_fps,
          ["-c:v", "libwebp_anim", "-lossless", "0", "-q:v", str(args.quality),
           "-loop", "0"], width=args.webp_width)
    print(f"{webp}: {seconds:.1f} s at {args.webp_fps} fps, "
          f"{args.webp_width} px, {webp.stat().st_size / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
