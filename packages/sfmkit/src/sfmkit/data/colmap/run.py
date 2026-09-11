"""Run COLMAP through pycolmap, on its own features or on sfmkit's matches.

Both variants share the reconstruction: COLMAP's incremental mapping on the
scene's photos, then, in a second pass, the query placed in that model with
every other camera held fixed, as sfmkit's localize does. What they write is
the same: the largest model as text, beside COLMAP's database, naming images
as sfmkit does, without extension.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pycolmap

from sfmkit.core.types import Matches
from sfmkit.data.io import image_file

__all__ = ["ColmapSummary", "colmap_device", "run_colmap", "run_colmap_on_matches"]

# An old photograph shares few matches with modern ones (32 SIFT matches at best
# on Valencia): with COLMAP's default minimum of 30 inliers it is never placed.
QUERY_MIN_INLIERS = 15


@dataclass
class ColmapSummary:
    """What a COLMAP run registered, for the stage to report.

    It stands in for pycolmap's own Reconstruction, which stays in this package.
    """

    registered: list[str]  # image names, without extension
    missing: list[str]  # asked for, but not registered
    n_points: int
    reprojection_error: float  # mean, in pixels
    query_registered: bool = False
    query_points: int = 0  # 3D points the query sees, if registered
    device: str = "cpu"  # where COLMAP's features and matching ran; mapping is CPU only


def colmap_device() -> str:
    """``cuda`` when this pycolmap is built for CUDA and sees a GPU, else ``cpu``."""
    has_gpu = bool(pycolmap.has_cuda) and pycolmap.get_num_cuda_devices() > 0
    return "cuda" if has_gpu else "cpu"


def run_colmap(scene_dir, images: list[str], out_dir, *, query: str | None = None,
               K: np.ndarray | None = None) -> ColmapSummary:
    """COLMAP on its own: SIFT features and exhaustive matching, then mapping.

    ``K`` fixes the camera of ``images``; without it COLMAP calibrates it.
    """
    work = _prepare(scene_dir, images, query, out_dir)
    device = colmap_device()
    on = pycolmap.Device.cuda if device == "cuda" else pycolmap.Device.cpu
    pycolmap.extract_features(work.database, work.scene_dir, image_names=work.files(images),
                              camera_mode=pycolmap.CameraMode.SINGLE, reader_options=_reader(K),
                              device=on)
    pycolmap.match_exhaustive(work.database, device=on)

    def add_query() -> None:
        pycolmap.extract_features(work.database, work.scene_dir, image_names=work.files([query]),
                                  camera_mode=pycolmap.CameraMode.PER_IMAGE, device=on)
        pycolmap.match_exhaustive(work.database, device=on)

    return _reconstruct(work, K, add_query if query else None, device)


def run_colmap_on_matches(scene_dir, images: list[str], matches: list[Matches], out_dir, *,
                          query: str | None = None, K: np.ndarray | None = None) -> ColmapSummary:
    """COLMAP's mapping alone, on sfmkit's keypoints and verified matches.

    COLMAP gets the input sfmkit's own reconstruction gets, so the two differ in
    the reconstruction alone. ``K`` fixes the camera of ``images``.
    """
    work = _prepare(scene_dir, images, query, out_dir)
    keypoints = _keypoints(matches)
    ours = [m for m in matches if work.has(m)]
    with_query = [m for m in ours if query in (m.image0, m.image1)]
    pycolmap.Database.open(work.database).close()  # import_images wants it to exist
    pycolmap.import_images(work.database, work.scene_dir, camera_mode=pycolmap.CameraMode.SINGLE,
                           image_names=work.files(images), options=_reader(K))
    _write(work, keypoints, [m for m in ours if m not in with_query])

    def add_query() -> None:
        pycolmap.import_images(work.database, work.scene_dir,
                               camera_mode=pycolmap.CameraMode.PER_IMAGE,
                               image_names=work.files([query]))
        _write(work, keypoints, with_query)

    return _reconstruct(work, K, add_query if query else None, "cpu")


@dataclass(frozen=True)
class _Workspace:
    """One COLMAP run: where it reads and writes, and its images' files."""

    scene_dir: Path
    out_dir: Path
    images: tuple[str, ...]
    query: str | None
    file: dict[str, str]  # image name, without extension, to its file in scene_dir

    @property
    def database(self) -> Path:
        return self.out_dir / "database.db"

    @property
    def name(self) -> dict[str, str]:
        return {f: n for n, f in self.file.items()}

    def files(self, names) -> list[str]:
        return [self.file[n] for n in names]

    def has(self, m: Matches) -> bool:
        return m.image0 in self.file and m.image1 in self.file


def _prepare(scene_dir, images: list[str], query: str | None, out_dir) -> _Workspace:
    """Find each image's file, and empty the ground for a new database."""
    pycolmap.logging.minloglevel = pycolmap.logging.ERROR  # ~100 lines of progress otherwise
    scene_dir, out_dir = Path(scene_dir), Path(out_dir)
    # COLMAP names an image by its file; sfmkit, without extension.
    every = [*images, *([query] if query else [])]
    work = _Workspace(scene_dir, out_dir, tuple(images), query,
                      {n: image_file(scene_dir, n).name for n in every})
    out_dir.mkdir(parents=True, exist_ok=True)
    work.database.unlink(missing_ok=True)
    return work


def _reconstruct(work: _Workspace, K: np.ndarray | None,
                 add_query: Callable[[], None] | None, device: str) -> ColmapSummary:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        rec = _largest(pycolmap.incremental_mapping(work.database, work.scene_dir, tmp / "scene",
                                                    options=_scene_pass(K)))
        if add_query is not None:
            rec = _place_query(rec, work, add_query, tmp)

    for image in rec.images.values():
        image.name = work.name[image.name]
    rec.write_text(work.out_dir)
    return _summary(rec, work.images, work.query, device)


def _place_query(rec, work: _Workspace, add_query: Callable[[], None], tmp: Path):
    """``rec`` with the query placed in it, every other pose and camera unchanged.

    pycolmap only estimates a new image's focal length when bundle adjustment
    may refine focal lengths, which lets it nudge the existing cameras too (by
    0.03% when K is given); they are put back afterwards. Their poses are held
    fixed throughout.
    """
    cameras = {c.camera_id: np.array(c.params) for c in rec.cameras.values()}
    model = tmp / "without_query"
    model.mkdir()
    rec.write(model)
    add_query()
    models = pycolmap.incremental_mapping(work.database, work.scene_dir, tmp / "with_query",
                                          input_path=model, options=_query_pass())
    if not models:
        return rec
    rec = _largest(models)
    for camera_id, params in cameras.items():
        rec.cameras[camera_id].params = params
    return rec


def _reader(K: np.ndarray | None) -> pycolmap.ImageReaderOptions:
    """How COLMAP sets up the camera: its own guess, or ``K`` as given."""
    options = pycolmap.ImageReaderOptions()
    if K is not None:
        # COLMAP puts the centre of the first pixel at 0.5, OpenCV's K at 0.
        options.camera_model = "PINHOLE"
        options.camera_params = f"{K[0, 0]},{K[1, 1]},{K[0, 2] + 0.5},{K[1, 2] + 0.5}"
    return options


def _scene_pass(K: np.ndarray | None) -> pycolmap.IncrementalPipelineOptions:
    options = pycolmap.IncrementalPipelineOptions()
    if K is not None:  # a given camera is not re-estimated
        options.ba_refine_focal_length = False
        options.ba_refine_principal_point = False
        options.ba_refine_extra_params = False
    return options


def _query_pass() -> pycolmap.IncrementalPipelineOptions:
    """The existing poses held fixed, and the query placed from few matches.

    The principal point is refined too, as localize's DLT frees it: an old
    photograph need not have it at the centre (a view camera's rising front, a
    cropped print), and pinned there COLMAP tilts the camera instead. On
    Valencia's Img00, pinned: looking 11° up, 11.5° from localize; refined: the
    principal point 125 px below the centre, the camera level, 1.2° from
    localize. The existing cameras are put back afterwards, so only the query's
    moves.
    """
    options = pycolmap.IncrementalPipelineOptions(fix_existing_frames=True)
    options.ba_refine_principal_point = True
    options.mapper.abs_pose_min_num_inliers = QUERY_MIN_INLIERS
    options.mapper.abs_pose_min_inlier_ratio = 0.1
    return options


def _largest(models: dict):
    if not models:
        raise RuntimeError("COLMAP registered no images")
    return max(models.values(), key=lambda r: r.num_reg_images())


def _keypoints(matches: list[Matches]) -> dict[str, np.ndarray]:
    """Each image's keypoints. Every pair of an image carries the same ones."""
    out: dict[str, np.ndarray] = {}
    for m in matches:
        for name, kp in ((m.image0, m.keypoints0), (m.image1, m.keypoints1)):
            if name in out and not np.array_equal(out[name], kp):
                raise ValueError(f"the keypoints of {name} differ between pairs")
            out[name] = kp
    return out


def _write(work: _Workspace, keypoints: dict[str, np.ndarray], matches: list[Matches]) -> None:
    """Write keypoints and verified matches into COLMAP's database."""
    db = pycolmap.Database.open(work.database)
    try:
        ids = {image.name: image.image_id for image in db.read_all_images()}
        for name in {n for m in matches for n in (m.image0, m.image1)}:
            image_id = ids[work.file[name]]
            if not db.exists_keypoints(image_id):
                # COLMAP puts the centre of the first pixel at 0.5, sfmkit at 0.
                db.write_keypoints(image_id, (keypoints[name] + 0.5).astype(np.float32))
        for m in matches:
            geometry = pycolmap.TwoViewGeometry()
            geometry.config = pycolmap.TwoViewGeometryConfiguration.UNCALIBRATED
            pairs = m.pairs if m.inliers is None else m.pairs[m.inliers]
            geometry.inlier_matches = pairs.astype(np.uint32)
            db.write_two_view_geometry(ids[work.file[m.image0]], ids[work.file[m.image1]], geometry)
    finally:
        db.close()


def _summary(rec, images, query: str | None, device: str) -> ColmapSummary:
    posed = {image.name: image for image in rec.images.values() if image.has_pose}
    registered = sorted(n for n in posed if n != query)
    return ColmapSummary(
        registered=registered,
        missing=sorted(set(images) - set(registered)),
        n_points=rec.num_points3D(),
        reprojection_error=rec.compute_mean_reprojection_error(),
        query_registered=query in posed,
        query_points=posed[query].num_points3D if query in posed else 0,
        device=device,
    )
