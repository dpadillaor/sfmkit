import numpy as np
import pytest

from sfmview.domain import Camera, Model, RunId, assemble_scene, camera_frame, shared_frame
from synthetic import moved, rotation, world


def model(source, cameras, points, query=None):
    return Model(source, tuple(Camera(n, R, t, query=n == query) for n, R, t in cameras), points)


def apply(T, X):
    return X @ T[:3, :3].T + T[:3, 3]


@pytest.fixture
def pair():
    """COLMAP's scene, and sfmkit's: the same, a similarity away, at half scale."""
    cameras, points = world()
    ours, our_points = moved(cameras, points, 0.5, rotation([1, 2, 3], 30), np.array([1.0, -2, 3]))
    return model("sfmkit", ours, our_points), model("colmap", cameras, points)


def test_camera_frame_puts_the_camera_at_the_origin():
    R, t = rotation([0, 1, 0], 20), np.array([1.0, 2, 3])
    camera = Camera("a", R, t)
    assert np.allclose(apply(camera_frame(camera), camera.center), 0)


def test_both_models_land_on_each_other(pair):
    ours, theirs = pair
    T_ours, T_theirs = shared_frame(ours, theirs, "Img02")
    assert np.allclose(apply(T_ours, ours.points), apply(T_theirs, theirs.points))
    for a, b in zip(ours.cameras, theirs.cameras, strict=True):
        assert np.allclose(apply(T_ours, a.center), apply(T_theirs, b.center))


def test_the_shared_frame_is_ours_at_our_scale(pair):
    ours, theirs = pair
    T_ours, _ = shared_frame(ours, theirs, "Img02")
    assert np.allclose(T_ours, camera_frame(ours.camera("Img02")))


def test_any_shared_camera_can_fix_the_scale(pair):
    ours, theirs = pair
    for name in ("Img12", "Img14"):
        T_ours, T_theirs = shared_frame(ours, theirs, "Img02", scale_image=name)
        assert np.allclose(apply(T_ours, ours.points), apply(T_theirs, theirs.points))


def test_the_query_does_not_fix_the_scale():
    cameras, points = world()
    ours = model("sfmkit", cameras[:1] + [("Img00", *cameras[1][1:])], points, query="Img00")
    theirs = model("colmap", cameras[:1] + [("Img00", cameras[1][1], 3 * cameras[1][2])], points)
    _, T_theirs = shared_frame(ours, theirs, "Img02")
    assert np.allclose(T_theirs, camera_frame(theirs.camera("Img02")))  # scale left at 1


def test_a_reference_missing_from_one_model_is_refused(pair):
    ours, theirs = pair
    with pytest.raises(ValueError, match="Img99"):
        shared_frame(ours, theirs, "Img99")


def test_the_dense_cloud_follows_colmap(pair):
    ours, theirs = pair
    scene = assemble_scene(RunId("city", "full"), ours, theirs, reference="Img02", dense=True)
    colmap = next(m for m in scene.models if m.source == "colmap")
    assert scene.dense_to_common is colmap.to_common


def test_no_dense_cloud_no_transform(pair):
    ours, theirs = pair
    assert assemble_scene(RunId("city", "full"), ours, theirs).dense_to_common is None


def test_the_reference_defaults_to_our_first_camera(pair):
    ours, theirs = pair
    scene = assemble_scene(RunId("city", "full"), ours, theirs)
    assert scene.reference == "Img02"
    a, b = scene.models
    assert np.allclose(apply(a.to_common, a.points), apply(b.to_common, b.points))


def test_models_without_a_common_camera_keep_their_frames(pair):
    ours, theirs = pair
    scene = assemble_scene(RunId("city", "full"), ours, theirs, reference="Img99")
    assert all(np.allclose(m.to_common, np.eye(4)) for m in scene.models)


def test_a_lone_model_is_shown_from_its_reference(pair):
    _, theirs = pair
    scene = assemble_scene(RunId("city", "full"), None, theirs, reference="Img02")
    (only,) = scene.models
    assert np.allclose(only.to_common, camera_frame(theirs.camera("Img02")))
