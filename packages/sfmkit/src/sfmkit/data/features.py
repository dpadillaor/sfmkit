"""Feature detection and matching with SuperPoint and LightGlue."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import numpy as np

from sfmkit.core.orientation import to_stored, upright
from sfmkit.core.types import Matches
from sfmkit.data.exif import read_orientation
from sfmkit.data.io import image_file, read_image, save_matches

__all__ = [
    "DEVICES", "WEIGHTS", "WeightsUnavailable", "match_pairs", "missing_weights", "pick_device",
    "resolve_device", "weights_dir", "weights_help",
]


class WeightsUnavailable(RuntimeError):
    """Matching's weights are neither downloaded nor reachable. Its message says what to do."""

DEVICES = ("auto", "cpu", "cuda")

# The weights matching needs, and where they come from. They are not shipped
# with sfmkit: SuperPoint's are Magic Leap's, licensed for noncommercial
# research and not to be redistributed, so whoever matches downloads them and
# takes those terms on themselves.
RELEASE = "https://github.com/cvg/LightGlue/releases/download/v0.1_arxiv"
WEIGHTS = {
    "superpoint_v1.pth": f"{RELEASE}/superpoint_v1.pth",
    "superpoint_lightglue_v0-1_arxiv.pth": f"{RELEASE}/superpoint_lightglue_v0-1_arxiv.pth",
}


def weights_dir() -> Path:
    """Where torch keeps downloaded weights: ``$TORCH_HOME/hub/checkpoints``.

    Read without importing torch, which costs a second, and by torch's own
    rule so the two always agree.
    """
    home = os.environ.get("TORCH_HOME")
    if not home:
        cache = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
        home = Path(cache) / "torch"
    return Path(home) / "hub" / "checkpoints"


def missing_weights() -> list[str]:
    """Those of ``WEIGHTS`` that are not downloaded yet."""
    where = weights_dir()
    return [name for name in WEIGHTS if not (where / name).is_file()]


def in_container() -> bool:
    return Path("/.dockerenv").exists()


def weights_help() -> str:
    """What to do when the weights are missing and cannot be fetched."""
    where = weights_dir()
    lines = [f"no SuperPoint and LightGlue weights in {where}, and they could not be downloaded."]
    if in_container():
        lines += [
            "That directory is what compose mounts, so tell it where they are:",
            "  - weights you already have: SFMKIT_WEIGHTS=/home/you/.cache/torch in .env",
            "  - or let Docker keep them: leave SFMKIT_WEIGHTS unset and its volume holds them",
            "  - plain docker run: -v ~/.cache/torch:/opt/torch",
        ]
    else:
        lines.append("Set TORCH_HOME to the directory that holds them, or let this download them.")
    lines.append("To fetch them by hand, into that directory:")
    lines += [f"  {url}" for url in WEIGHTS.values()]
    lines.append("SuperPoint's weights are Magic Leap's: noncommercial research use only.")
    return "\n".join(lines)


def resolve_device(requested: str, cuda_available: bool) -> str:
    """``auto`` becomes ``cuda`` when there is a GPU, else ``cpu``.

    Asking for ``cuda`` without a GPU is an error rather than a silent fall back
    to ``cpu``, because the two give slightly different matches.
    """
    if requested not in DEVICES:
        raise ValueError(f"device must be one of {DEVICES}, not {requested!r}")
    if requested == "auto":
        return "cuda" if cuda_available else "cpu"
    if requested == "cuda" and not cuda_available:
        raise ValueError("device 'cuda' requested, but PyTorch sees no GPU")
    return requested


def pick_device(requested: str = "auto") -> str:
    """``resolve_device`` against the GPUs PyTorch can actually see."""
    import torch

    return resolve_device(requested, torch.cuda.is_available())


def match_pairs(
    images_dir: Path,
    pairs: list[tuple[str, str]],
    out_dir: Path,
    *,
    max_keypoints: int = 2048,
    device: str = "auto",
    on_pair: Callable[[str, str, int], None] | None = None,
    on_download: Callable[[list[str], Path], None] | None = None,
) -> list[Path]:
    """Extract features once per image and match every requested pair.

    Features are cached across pairs: an exhaustive graph over N images has
    N(N-1)/2 pairs but needs only N extractions. The weights are downloaded on
    first use, ``on_download`` told first; without a network, the error says
    where they go and how to point at them.
    """
    import torch
    from lightglue import LightGlue, SuperPoint
    from lightglue.utils import numpy_image_to_torch, rbd

    torch.set_grad_enabled(False)
    dev = torch.device(pick_device(device))
    missing = missing_weights()
    if missing and on_download is not None:
        on_download(missing, weights_dir())
    try:
        extractor = SuperPoint(max_num_keypoints=max_keypoints).eval().to(dev)
        matcher = LightGlue(features="superpoint").eval().to(dev)
    except OSError as no_weights:  # no network, or nowhere to write them
        raise WeightsUnavailable(weights_help()) from no_weights

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    images_dir = Path(images_dir)

    cache: dict[str, tuple] = {}

    def features(name: str) -> tuple:
        """An image's features, found upright; and how to put them back as stored."""
        if name not in cache:
            path = image_file(images_dir, name)
            stored = read_image(path)
            turn = read_orientation(path)
            rgb = np.ascontiguousarray(upright(stored, turn)[..., ::-1])
            size = (stored.shape[1], stored.shape[0])
            cache[name] = (extractor.extract(numpy_image_to_torch(rgb).to(dev)), turn, size)
        return cache[name]

    written: list[Path] = []
    for a, b in pairs:
        (f0, turn0, size0), (f1, turn1, size1) = features(a), features(b)
        m01 = matcher({"image0": f0, "image1": f1})
        r0, r1, rm = (rbd(x) for x in (f0, f1, m01))
        matches = Matches(
            image0=a,
            image1=b,
            keypoints0=to_stored(r0["keypoints"].cpu().numpy(), turn0, size0),
            keypoints1=to_stored(r1["keypoints"].cpu().numpy(), turn1, size1),
            pairs=rm["matches"].cpu().numpy().astype(np.intp),
            scores=rm["scores"].cpu().numpy(),
        )
        path = out_dir / f"{a}__{b}.npz"
        save_matches(matches, path)
        written.append(path)
        if on_pair is not None:
            on_pair(a, b, matches.n_matches)
    return written
