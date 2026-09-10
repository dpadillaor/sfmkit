"""COLMAP's dense reconstruction: multi-view stereo on a sparse model's views."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import pycolmap

from sfmkit.data.io import image_file

__all__ = ["NO_CUDA", "DenseSummary", "dense_available", "run_dense"]

NO_CUDA = ("the dense reconstruction needs CUDA: install requirements-gpu.txt, "
           "on a machine with an NVIDIA GPU")


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
    return bool(pycolmap.has_cuda) and pycolmap.get_num_cuda_devices() > 0


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
