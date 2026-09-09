"""Invariants and known-answer tests for the geometry primitives."""

import numpy as np
import pytest

from sfmkit.core.geometry import (
    decompose_projection,
    eight_point,
    fundamental_to_essential,
    log_rotation,
    normalize_points,
    project,
    recover_pose,
    rodrigues,
    sampson_distance,
    skew,
    triangulate_multi_view,
    triangulate_two_view,
)
from sfmkit.core.types import Pose


class TestRotations:
    def test_rodrigues_produces_a_valid_rotation(self, rng):
        for _ in range(50):
            R = rodrigues(rng.normal(size=3) * 2.0)
            assert np.allclose(R @ R.T, np.eye(3), atol=1e-12)
            assert np.isclose(np.linalg.det(R), 1.0)

    def test_rodrigues_matches_matrix_exponential(self, rng):
        """The closed form must equal scipy's general expm, not merely approximate it."""
        from scipy.linalg import expm
        for _ in range(50):
            w = rng.normal(size=3) * 1.5
            assert np.allclose(rodrigues(w), expm(skew(w)), atol=1e-12)

    def test_log_inverts_rodrigues(self, rng):
        for _ in range(50):
            w = rng.normal(size=3)
            w = w / np.linalg.norm(w) * rng.uniform(0.01, 3.0)
            assert np.allclose(rodrigues(log_rotation(rodrigues(w))), rodrigues(w), atol=1e-9)

    def test_zero_and_pi_are_handled(self):
        assert np.allclose(rodrigues(np.zeros(3)), np.eye(3))
        assert np.allclose(log_rotation(np.eye(3)), np.zeros(3))
        R = rodrigues(np.array([np.pi, 0.0, 0.0]))
        assert np.allclose(rodrigues(log_rotation(R)), R, atol=1e-6)


class TestNormalization:
    def test_centroid_at_origin_and_mean_distance_sqrt2(self, rng):
        x = rng.normal(500, 200, size=(100, 2))
        n, T = normalize_points(x)
        assert np.allclose(n.mean(axis=0), 0, atol=1e-9)
        assert np.isclose(np.linalg.norm(n, axis=1).mean(), np.sqrt(2))
        h = np.hstack([x, np.ones((len(x), 1))]) @ T.T
        assert np.allclose(h[:, :2], n, atol=1e-9)


class TestFundamental:
    def test_rank_two(self, scene):
        m = scene.matches_for("cam00", "cam02")
        x0, x1 = m.points()
        assert np.linalg.matrix_rank(eight_point(x0, x1), tol=1e-6) == 2

    def test_exact_on_noiseless_correspondences(self, scene):
        """With perfect data, every point must lie on its epipolar line."""
        m = scene.matches_for("cam00", "cam02")
        x0, x1 = m.points()
        F = eight_point(x0, x1)
        assert sampson_distance(F, x0, x1).max() < 1e-6

    def test_needs_eight_points(self, rng):
        with pytest.raises(ValueError):
            eight_point(rng.normal(size=(7, 2)), rng.normal(size=(7, 2)))

    def test_agrees_with_opencv(self, scene):
        """OpenCV as an external oracle -- the check the original left in a notebook."""
        cv2 = pytest.importorskip("cv2")
        m = scene.matches_for("cam00", "cam02", noise=0.3, seed=1)
        x0, x1 = m.points()
        F_ours = eight_point(x0, x1)
        F_cv, _ = cv2.findFundamentalMat(x0, x1, cv2.FM_8POINT)
        ours = sampson_distance(F_ours, x0, x1).mean()
        theirs = sampson_distance(F_cv / np.linalg.norm(F_cv), x0, x1).mean()
        assert ours < theirs * 1.5 + 0.1


class TestPoseRecovery:
    def test_recovers_the_true_relative_pose(self, scene):
        m = scene.matches_for("cam00", "cam02")
        x0, x1 = m.points()
        E = fundamental_to_essential(eight_point(x0, x1), scene.K, scene.K)
        pose = recover_pose(E, scene.K, x0, x1)
        truth = scene.true_relative("cam02", "cam00")

        from sfmkit.core.metrics import rotation_error_deg
        assert rotation_error_deg(pose.R, truth.R) < 0.5
        # Translation is only known up to scale, so compare directions.
        a = pose.t / np.linalg.norm(pose.t)
        b = truth.t / np.linalg.norm(truth.t)
        assert abs(a @ b) > 0.999


class TestTriangulation:
    def test_two_view_recovers_known_points(self, scene):
        m = scene.matches_for("cam00", "cam02")
        x0, x1 = m.points()
        p0, p1 = scene.poses["cam00"], scene.poses["cam02"]
        X = triangulate_two_view(x0, x1, scene.K, p0, scene.K, p1)
        truth = scene.points[np.intersect1d(scene.visible["cam00"], scene.visible["cam02"])]
        assert np.abs(X - truth).max() < 1e-6

    def test_multi_view_beats_two_view_under_noise(self, scene):
        """The reason tracks matter: more views condition depth better.

        Averaged over every point all five cameras see -- a single point could
        get lucky, the median could not.
        """
        rng = np.random.default_rng(0)
        common = scene.visible[scene.images[0]]
        for img in scene.images[1:]:
            common = np.intersect1d(common, scene.visible[img])
        assert len(common) > 20, "scene should have points visible everywhere"

        err_2, err_all = [], []
        for pid in common:
            obs = []
            for img in scene.images:
                k = int(np.flatnonzero(scene.visible[img] == pid)[0])
                uv = scene.keypoints[img][k] + rng.normal(0, 1.0, 2)
                obs.append((uv, scene.poses[img].projection_matrix(scene.K)))
            truth = scene.points[pid]
            err_2.append(np.linalg.norm(triangulate_multi_view(obs[:2]) - truth))
            err_all.append(np.linalg.norm(triangulate_multi_view(obs) - truth))
        assert np.median(err_all) < np.median(err_2)

    def test_needs_two_views(self):
        with pytest.raises(ValueError):
            triangulate_multi_view([(np.zeros(2), np.eye(3, 4))])


class TestProjection:
    def test_round_trip(self, scene):
        uv = project(scene.points, scene.K, scene.poses["cam00"])
        idx = scene.visible["cam00"]
        assert np.abs(uv[idx] - scene.keypoints["cam00"]).max() < 1e-9

    def test_points_behind_the_camera_are_nan(self, scene):
        behind = np.array([[0.0, 0.0, -5.0]])
        assert np.isnan(project(behind, scene.K, Pose.identity())).all()


class TestDecomposeProjection:
    def test_round_trip(self, scene):
        pose = scene.poses["cam02"]
        K, recovered = decompose_projection(pose.projection_matrix(scene.K))
        assert np.allclose(K, scene.K, atol=1e-6)
        assert np.allclose(recovered.R, pose.R, atol=1e-6)
        assert np.allclose(recovered.t, pose.t, atol=1e-6)


class TestPoseNormalisation:
    """Whatever a caller passes, `Pose` stores one canonical form."""

    def test_accepts_lists_and_other_dtypes(self):
        p = Pose([[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0, 0, 5])
        assert p.R.shape == (3, 3) and p.R.dtype == np.float64
        assert p.t.shape == (3,) and p.t.dtype == np.float64
        assert np.allclose(Pose(np.eye(3, dtype=np.float32), [0, 0, 1]).R, np.eye(3))

    def test_rejects_a_wrongly_shaped_rotation(self):
        """Nine loose numbers are far more likely a bug than an intent."""
        with pytest.raises(ValueError, match=r"R must be \(3, 3\)"):
            Pose(np.arange(9.0), [0, 0, 1])
        with pytest.raises(ValueError, match=r"R must be \(3, 3\)"):
            Pose(np.eye(4), [0, 0, 1])

    def test_rejects_a_wrongly_sized_translation(self):
        with pytest.raises(ValueError, match="t must have 3 elements"):
            Pose(np.eye(3), [0, 0])

    def test_validate_catches_non_rotations(self):
        Pose(np.eye(3), [0, 0, 1]).validate()
        rodrigues(np.array([0.3, -0.2, 1.1])).view()  # sanity: rotations validate
        Pose(rodrigues(np.array([0.3, -0.2, 1.1])), [0, 0, 1]).validate()

        with pytest.raises(ValueError, match="not orthonormal"):
            Pose(np.array([[1.0, 2, 3], [4, 5, 6], [7, 8, 9]]), [0, 0, 1]).validate()
        with pytest.raises(ValueError, match="reflection"):
            Pose(np.diag([1.0, 1.0, -1.0]), [0, 0, 1]).validate()

    def test_validate_returns_self_so_it_chains(self):
        p = Pose(np.eye(3), [0, 0, 1])
        assert p.validate() is p

    def test_flattens_column_and_row_translations(self):
        """cv2.solvePnP returns t as (3, 1); downstream code should not have to know."""
        for t in ([0, 0, 5], np.array([[0], [0], [5]]), np.array([[0, 0, 5]])):
            assert Pose(np.eye(3), t).t.shape == (3,)

    def test_is_immutable(self):
        import dataclasses
        p = Pose(np.eye(3), [0, 0, 5])
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.R = np.zeros((3, 3))

    def test_centre_is_not_the_translation(self):
        """The classic sign error: t is not where the camera is."""
        p = Pose(np.eye(3), [0, 0, 5])
        assert np.allclose(p.t, [0, 0, 5])
        assert np.allclose(p.center, [0, 0, -5])

    def test_equality_compares_values(self):
        """The generated __eq__ raises on numpy fields; this one must not."""
        a, b = Pose(np.eye(3), [0, 0, 5]), Pose(np.eye(3), [0, 0, 5])
        assert a == b
        assert a in [b]
        assert a != Pose(np.eye(3), [0, 0, 6])
        assert a.__eq__("not a pose") is NotImplemented
