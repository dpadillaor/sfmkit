"""The file readers: COLMAP's text model and sfmkit's npz files."""

import numpy as np

from sfmview.adapters.colmap_text import read_colmap
from sfmview.adapters.sfmkit_files import read_reconstruction
from synthetic import SIZE, K, rotation, world, write_colmap, write_reconstruction


def test_colmap_poses_points_and_cameras_are_read_back(tmp_path):
    cameras, points = world()
    colors = np.arange(len(points) * 3).reshape(-1, 3) % 256
    write_colmap(tmp_path, cameras, points, colors)
    model = read_colmap(tmp_path)

    assert model.source == "colmap"
    assert [c.name for c in model.cameras] == [n for n, _, _ in cameras]
    for c, (_, R, t) in zip(model.cameras, cameras, strict=True):
        assert np.allclose(c.R, R) and np.allclose(c.t, t)
        assert np.allclose(c.K, K) and c.size == SIZE
    assert np.allclose(model.points, points)
    assert model.colors.dtype == np.uint8 and np.array_equal(model.colors, colors)


def test_colmap_single_focal_models_share_it(tmp_path):
    cameras, points = world()
    write_colmap(tmp_path, cameras, points)
    (tmp_path / "cameras.txt").write_text("1 SIMPLE_RADIAL 557 418 597.8 278.5 209 0.08\n")
    c = read_colmap(tmp_path).cameras[0]
    assert c.K[0, 0] == c.K[1, 1] == 597.8
    assert (c.K[0, 2], c.K[1, 2]) == (278.5, 209) and c.size == (557, 418)


def test_colmap_marks_the_query(tmp_path):
    cameras, points = world()
    write_colmap(tmp_path, cameras, points)
    assert [c.name for c in read_colmap(tmp_path, query="Img13").cameras if c.query] == ["Img13"]


def test_colmap_images_without_2d_points_keep_the_pairs_aligned(tmp_path):
    """The second line of an image is empty when it has no 2D points."""
    cameras, points = world()
    write_colmap(tmp_path, cameras, points)  # every image line is followed by an empty one
    assert len(read_colmap(tmp_path).cameras) == len(cameras)


def test_sfmkit_reconstruction_and_query(tmp_path):
    cameras, points = world()
    write_reconstruction(tmp_path / "reconstruction.npz", cameras, points)
    R, t, K_q = rotation([0, 0, 1], 5), np.array([0.1, 0, 0]), np.diag([600.0, 600, 1])
    K_q[:2, 2] = [300, 200]
    np.savez(tmp_path / "query_pose.npz", R=R, t=t, K=K_q)

    model = read_reconstruction(tmp_path / "reconstruction.npz", tmp_path / "query_pose.npz",
                                "Img00")
    assert model.source == "sfmkit" and model.colors is None
    assert [c.name for c in model.cameras] == [n for n, _, _ in cameras] + ["Img00"]
    query = model.cameras[-1]
    assert query.query and np.allclose(query.R, R) and np.allclose(query.K, K_q)
    assert model.cameras[0].size == (640, 480)  # guessed from K's principal point
    assert np.allclose(model.points, points)


def test_sfmkit_query_without_k_or_without_file(tmp_path):
    cameras, points = world()
    write_reconstruction(tmp_path / "reconstruction.npz", cameras, points)
    np.savez(tmp_path / "query_pose.npz", R=np.eye(3), t=np.zeros(3))
    with_query = read_reconstruction(tmp_path / "reconstruction.npz",
                                     tmp_path / "query_pose.npz", "Img00")
    assert with_query.cameras[-1].K is None and with_query.cameras[-1].size is None
    without = read_reconstruction(tmp_path / "reconstruction.npz", tmp_path / "missing.npz",
                                  "Img00")
    assert not any(c.query for c in without.cameras)
