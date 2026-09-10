"""Feature detection and matching with SuperPoint and LightGlue."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np

from sfmkit.core.types import Matches
from sfmkit.data.io import save_matches

__all__ = ["DEVICES", "match_pairs", "pick_device", "resolve_device"]

DEVICES = ("auto", "cpu", "cuda")


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
) -> list[Path]:
    """Extract features once per image and match every requested pair.

    Features are cached across pairs: an exhaustive graph over N images has
    N(N-1)/2 pairs but needs only N extractions.
    """
    import torch
    from lightglue import LightGlue, SuperPoint
    from lightglue.utils import load_image, rbd

    torch.set_grad_enabled(False)
    dev = torch.device(pick_device(device))
    extractor = SuperPoint(max_num_keypoints=max_keypoints).eval().to(dev)
    matcher = LightGlue(features="superpoint").eval().to(dev)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    images_dir = Path(images_dir)

    cache: dict[str, dict] = {}

    def features(name: str) -> dict:
        if name not in cache:
            candidates = [images_dir / name, *images_dir.glob(f"{name}.*")]
            path = next((c for c in candidates if c.is_file()), None)
            if path is None:
                raise FileNotFoundError(f"no image named {name} in {images_dir}")
            cache[name] = extractor.extract(load_image(path).to(dev))
        return cache[name]

    written: list[Path] = []
    for a, b in pairs:
        f0, f1 = features(a), features(b)
        m01 = matcher({"image0": f0, "image1": f1})
        r0, r1, rm = (rbd(x) for x in (f0, f1, m01))
        matches = Matches(
            image0=a,
            image1=b,
            keypoints0=r0["keypoints"].cpu().numpy(),
            keypoints1=r1["keypoints"].cpu().numpy(),
            pairs=rm["matches"].cpu().numpy().astype(np.intp),
            scores=rm["scores"].cpu().numpy(),
        )
        path = out_dir / f"{a}__{b}.npz"
        save_matches(matches, path)
        written.append(path)
        if on_pair is not None:
            on_pair(a, b, matches.n_matches)
    return written
