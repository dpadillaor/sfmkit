"""Writing a list of frames out as an animation, shared by the tools here.

Frames are BGR arrays, as OpenCV makes them, with a duration each in
milliseconds; a held frame costs a video almost nothing and a WebP one entry.
The typeface every figure is lettered in lives here too, for the same reason.
"""

import functools
import shutil
import subprocess
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

FORMATS = ("gif", "webp", "mp4", "all")

ROOT = Path(__file__).resolve().parents[1]
PLEX = ROOT / "packages/viewer/src/sfmview/web/vendor/fonts/ibmplexsans-latin.woff2"
GROUND = (16, 16, 16)  # the viewer's ground, so the figures of this project match


@functools.cache
def typeface() -> bytes:
    """The viewer's own IBM Plex Sans, as something PIL can open.

    The viewer keeps it as woff2, which PIL cannot read; fontTools decompresses
    it (through brotli) and writes it back out as TrueType, so the figures and
    the viewer are set in one typeface kept in one place. Without fontTools,
    matplotlib's DejaVu Sans.
    """
    try:
        from fontTools.ttLib import TTFont
        out = BytesIO()
        font = TTFont(PLEX)
        font.flavor = None
        font.save(out)
        return out.getvalue()
    except Exception:  # noqa: BLE001 - any of fontTools, brotli or the file
        import matplotlib
        return (Path(matplotlib.__file__).parent
                / "mpl-data/fonts/ttf/DejaVuSans.ttf").read_bytes()


def write_video(frames, times, out: Path, fps: int, crf: int = 23) -> Path:
    """H.264, the held frames repeated to fill their time.

    Trimmed to even dimensions first: the figure's height follows whatever
    width was asked for, and libx264 refuses an odd one by closing the pipe,
    which arrives here as a broken pipe and says nothing about why.
    """
    if shutil.which("ffmpeg") is None:
        raise SystemExit("no ffmpeg: install it, or ask for --format webp")
    height, width = (n - n % 2 for n in frames[0].shape[:2])
    frames = [f[:height, :width] for f in frames]
    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{width}x{height}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", str(crf),
         "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE)
    for frame, milliseconds in zip(frames, times, strict=True):
        for _ in range(max(1, round(milliseconds * fps / 1000))):
            ffmpeg.stdin.write(np.ascontiguousarray(frame).tobytes())
    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        raise SystemExit("ffmpeg failed")
    return out


def save(frames, times, out: Path, kind: str, *, fps: int = 12, quality: int = 70,
         colours: int = 96, crf: int = 23) -> list[Path]:
    """``frames`` as a WebP, a GIF, an MP4, or all three, named after ``out``."""
    out.parent.mkdir(parents=True, exist_ok=True)
    pictures = [Image.fromarray(f[..., ::-1]) for f in frames]
    written = []
    if kind in ("webp", "all"):
        path = out.with_suffix(".webp")
        pictures[0].save(path, save_all=True, append_images=pictures[1:], duration=times,
                         loop=0, quality=quality, method=6)
        written.append(path)
    if kind in ("gif", "all"):
        path = out.with_suffix(".gif")
        paletted = [p.convert("P", palette=Image.ADAPTIVE, colors=colours,
                              dither=Image.Dither.NONE) for p in pictures]
        paletted[0].save(path, save_all=True, append_images=paletted[1:], duration=times,
                         loop=0, optimize=True, disposal=2)
        written.append(path)
    if kind in ("mp4", "all"):
        written.append(write_video(frames, times, out.with_suffix(".mp4"), fps, crf))
    for path in written:
        print(f"{path}: {len(frames)} frames, {sum(times) / 1000:.1f}s, "
              f"{frames[0].shape[1]}x{frames[0].shape[0]}, {path.stat().st_size / 1e6:.2f} MB")
    return written
