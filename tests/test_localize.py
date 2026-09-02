"""Visual localisation of a query image against an existing reconstruction."""

import numpy as np
import pytest

from sfmkit.geometry import project
from sfmkit.localize import _query_to_map_correspondences, localize_image
from sfmkit.metrics import rotation_error_deg
from sfmkit.robust import ransac_dlt
from sfmkit.synthetic import make_scene
from sfmkit.types import Matches, Reconstruction, Track


@pytest.fixture(scope="module")
def mapped():
    """A ground-truth reconstruction of four cameras, plus a fifth to localise."""
    scene = make_scene(n_cameras=5, n_points=400, seed=3)
    mapped_images = scene.images[:4]
    query = scene.images[4]
    ref = mapped_images[0]

    poses = {n: scene.poses[n].relative_to(scene.poses[ref]) for n in mapped_images}
    points = scene.poses[ref].transform(scene.points)

    tracks = []
    for pid in range(len(scene.points)):
        obs = {}
        for img in mapped_images:
            k = np.flatnonzero(scene.visible[img] == pid)
            if len(k):
                obs[img] = int(k[0])
        tracks.append(Track(observations=obs))

    rec = Reconstruction(K=scene.K, poses=poses, points=points, tracks=tracks)
    matches = [scene.matches_for(img, query) for img in mapped_images]
    truth = scene.poses[query].relative_to(scene.poses[ref])
    return scene, rec, matches, query, truth


class TestCorrespondences:
    def test_lifts_matches_to_map_points(self, mapped):
        _, rec, matches, query, _ = mapped
        X, uv = _query_to_map_correspondences(rec, matches, query)
        assert len(X) == len(uv) > 100
        assert X.shape[1] == 3 and uv.shape[1] == 2

    def test_ignores_unregistered_images(self, mapped):
        _, rec, matches, query, _ = mapped
        stripped = Reconstruction(K=rec.K, poses={}, points=rec.points, tracks=rec.tracks)
        X, _ = _query_to_map_correspondences(stripped, matches, query)
        assert len(X) == 0


class TestLocalize:
    def test_recovers_the_query_pose_with_known_intrinsics(self, mapped):
        pytest.importorskip("cv2")
        _, rec, matches, query, truth = mapped
        r = localize_image(rec, matches, query, K=rec.K, seed=0)
        assert r is not None
        assert rotation_error_deg(r.pose.R, truth.R) < 1.0
        assert np.linalg.norm(r.pose.center - truth.center) < 0.1

    def test_recovers_pose_and_focal_when_intrinsics_are_unknown(self, mapped):
        """The historical-photograph case: eleven unknowns, solved by DLT."""
        scene, rec, matches, query, truth = mapped
        r = localize_image(rec, matches, query, K=None, seed=0)
        assert r is not None
        assert rotation_error_deg(r.pose.R, truth.R) < 2.0
        # The focal length is recovered, not assumed.
        assert abs(r.K[0, 0] - scene.K[0, 0]) / scene.K[0, 0] < 0.10

    def test_returns_none_without_enough_correspondences(self, mapped):
        _, rec, _, query, _ = mapped
        empty = Matches(query, "cam00", np.zeros((2, 2)), np.zeros((2, 2)),
                        np.zeros((0, 2), dtype=np.intp))
        assert localize_image(rec, [empty], query, seed=0) is None

    def test_is_deterministic_under_a_seed(self, mapped):
        _, rec, matches, query, _ = mapped
        a = localize_image(rec, matches, query, K=None, seed=11)
        b = localize_image(rec, matches, query, K=None, seed=11)
        assert np.allclose(a.pose.R, b.pose.R)
        assert np.allclose(a.pose.t, b.pose.t)


class TestRansacDlt:
    def test_recovers_a_known_projection_matrix(self):
        scene = make_scene(n_cameras=2, n_points=200, seed=5)
        pose = scene.poses["cam00"]
        P_true = pose.projection_matrix(scene.K)
        X = scene.points
        uv = project(X, scene.K, pose)
        ok = np.isfinite(uv).all(axis=1)

        res = ransac_dlt(X[ok], uv[ok], seed=0)
        assert res.converged
        P = res.model / np.linalg.norm(res.model) * np.linalg.norm(P_true)
        if np.sign(P.flat[np.argmax(np.abs(P))]) != np.sign(P_true.flat[np.argmax(np.abs(P_true))]):
            P = -P
        assert np.abs(P - P_true).max() / np.abs(P_true).max() < 1e-6

    def test_rejects_outliers(self):
        scene = make_scene(n_cameras=2, n_points=300, seed=6)
        pose = scene.poses["cam00"]
        X, uv = scene.points, project(scene.points, scene.K, pose)
        ok = np.isfinite(uv).all(axis=1)
        X, uv = X[ok], uv[ok]

        rng = np.random.default_rng(0)
        bad = rng.choice(len(X), len(X) // 4, replace=False)
        uv[bad] += rng.normal(0, 300, (len(bad), 2))

        res = ransac_dlt(X, uv, threshold=5.0, seed=0)
        assert res.converged
        assert not res.inliers[bad].any()

    def test_too_few_points(self):
        assert ransac_dlt(np.zeros((4, 3)), np.zeros((4, 2)), seed=0).model is None
