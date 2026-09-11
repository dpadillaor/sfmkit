"""COLMAP's dense reconstruction: multi-view stereo on a sparse model's views."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pycolmap

from sfmkit.data.colmap.run import colmap_device
from sfmkit.data.io import image_file

__all__ = ["NO_CUDA", "DenseSummary", "dense_available", "read_fused", "run_dense"]

NO_CUDA = ("the dense reconstruction needs an NVIDIA GPU and COLMAP built for it: "
           "requirements-gpu.txt or the gpu image, with the GPU visible "
           "(docker compose run cli-gpu)")


@dataclass
class DenseSummary:
    """What the dense reconstruction produced, for the stage to report."""

    n_images: int
    n_points: int


def dense_available() -> bool:
    """Whether PatchMatch stereo, which is CUDA only, can run here.

    A pycolmap built with CUDA is not enough: it also needs a GPU in sight,
    which a gpu image run without one does not have.
    """
    return colmap_device() == "cuda"


def run_dense(model_dir, scene_dir, images: list[str], out_dir, *,
              max_image_size: int = 2000) -> DenseSummary:
    """A dense point cloud of ``images``, from the sparse COLMAP model in ``model_dir``.

    Undistorts the images, runs PatchMatch stereo and fuses the depth maps into
    ``out_dir/fused.ply``. Other images of the model, such as the query, are
    left out. The workspace in between, depth maps and all, is discarded.
    """
    if not dense_available():
        raise RuntimeError(NO_CUDA)
    pycolmap.logging.minloglevel = pycolmap.logging.ERROR
    scene_dir, out_dir = Path(scene_dir), Path(out_dir)
    rec = pycolmap.Reconstruction(Path(model_dir))
    for image in list(rec.images.values()):
        if image.name not in images:
            # PatchMatch aborts the whole process on an image it has no undistorted copy of.
            rec.deregister_frame(image.frame_id)
        image.name = image_file(scene_dir, image.name).name  # COLMAP reads images by file

    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        sparse, workspace = Path(tmp) / "sparse", Path(tmp) / "workspace"
        sparse.mkdir()
        rec.write(sparse)
        options = pycolmap.UndistortCameraOptions()
        options.max_image_size = max_image_size
        pycolmap.undistort_images(workspace, sparse, scene_dir, undistort_options=options)
        pycolmap.patch_match_stereo(workspace)
        fused = pycolmap.stereo_fusion(out_dir / "fused.ply", workspace, output_type="PLY")
    return DenseSummary(n_images=rec.num_reg_images(), n_points=fused.num_points3D())


def read_fused(path) -> tuple[np.ndarray, np.ndarray]:
    """The points and colours of a dense cloud, ``(N, 3)`` each, from COLMAP's PLY.

    COLMAP writes a binary little-endian PLY of x, y, z, a normal and a colour
    per point; only the points and the colours are read. Anything else is
    refused rather than guessed at.
    """
    path = Path(path)
    with path.open("rb") as f:
        header, fields = [], []
        while True:
            line = f.readline().decode("ascii", "replace").strip()
            if not line:
                raise ValueError(f"{path.name}: no end of header")
            header.append(line)
            if line.startswith("property "):
                fields.append(line.split()[1:])
            if line == "end_header":
                break
            if line.startswith("element vertex "):
                count = int(line.split()[2])
        if "format binary_little_endian 1.0" not in header:
            raise ValueError(f"{path.name}: only a binary little-endian PLY is read")
        types = {"float": "<f4", "float32": "<f4", "double": "<f8", "uchar": "u1", "uint8": "u1"}
        try:
            dtype = np.dtype([(name, types[kind]) for kind, name in fields])
        except KeyError as unknown:
            raise ValueError(f"{path.name}: property type {unknown} is not read") from None
        rows = np.frombuffer(f.read(count * dtype.itemsize), dtype=dtype, count=count)
    missing = {"x", "y", "z", "red", "green", "blue"} - set(rows.dtype.names)
    if missing:
        raise ValueError(f"{path.name}: no {', '.join(sorted(missing))}")
    points = np.stack([rows["x"], rows["y"], rows["z"]], axis=1).astype(float)
    colours = np.stack([rows["red"], rows["green"], rows["blue"]], axis=1).astype(np.uint8)
    return points, colours
