"""End-to-end reconstruction against known ground truth.

These are the tests that matter: a synthetic scene has an exact answer, so the
whole pipeline can be checked without a single photograph, in seconds, in CI.
"""

import numpy as np
import pytest

from sfmkit.core.metrics import compare_poses
from sfmkit.core.reconstruct import ReconstructionConfig, reconstruct
from sfmkit.core.robust import ransac_fundamental
from sfmkit.core.tracks import build_tracks


def _verify(matches, seed=0, threshold=3.0):
    """Geometric verification, as the pipeline's `verify` stage would do."""
    out = []
    for m in matches:
        x0, x1 = m.keypoints0[m.pairs[:, 0]], m.keypoints1[m.pairs[:, 1]]
        res = ransac_fundamental(x0, x1, threshold=threshold, seed=seed)
        if res.converged and res.n_inliers >= 20:
            m.inliers = res.inliers
            out.append(m)
    return out


def _all_pairs(scene, **kw):
    return [
        scene.matches_for(a, b, **kw, seed=abs(hash((a, b))) % 2**31)
        for i, a in enumerate(scene.images)
        for b in scene.images[i + 1:]
    ]


def _star_pairs(scene, **kw):
    ref = scene.images[0]
    return [scene.matches_for(ref, b, **kw, seed=abs(hash((ref, b))) % 2**31)
            for b in scene.images[1:]]


class TestNoiselessReconstruction:
    def test_recovers_the_scene_exactly(self, scene):
        pytest.importorskip("cv2")
        matches = _verify(_all_pairs(scene))
        tracks = build_tracks(matches)
        result = reconstruct(matches, scene.K, tracks, ReconstructionConfig(seed=0))

        rec = result.reconstruction
        assert len(rec.poses) == len(scene.images), "every camera should register"
        assert rec.n_points > 200

        cmp = compare_poses(rec.poses, scene.poses, reference=rec.registered[0])
        assert cmp["mean_rotation_error_deg"] < 0.5
        assert cmp["max_rotation_error_deg"] < 1.0

    def test_final_rmse_is_subpixel(self, scene):
        pytest.importorskip("cv2")
        matches = _verify(_all_pairs(scene))
        result = reconstruct(matches, scene.K, build_tracks(matches), ReconstructionConfig(seed=0))
        assert result.reports[-1].rmse_after < 1.0


class TestNoisyReconstruction:
    def test_survives_noise_and_outliers(self, scene):
        pytest.importorskip("cv2")
        matches = _verify(_all_pairs(scene, noise=0.5, outlier_ratio=0.2), threshold=3.0)
        result = reconstruct(matches, scene.K, build_tracks(matches), ReconstructionConfig(seed=0))

        rec = result.reconstruction
        assert len(rec.poses) >= len(scene.images) - 1
        cmp = compare_poses(rec.poses, scene.poses, reference=rec.registered[0])
        assert cmp["mean_rotation_error_deg"] < 3.0

    def test_is_deterministic(self, scene):
        pytest.importorskip("cv2")
        matches = _verify(_all_pairs(scene, noise=0.5, outlier_ratio=0.2))
        tracks = build_tracks(matches)
        a = reconstruct(matches, scene.K, tracks, ReconstructionConfig(seed=0))
        b = reconstruct(matches, scene.K, tracks, ReconstructionConfig(seed=0))
        assert a.reconstruction.registered == b.reconstruction.registered
        assert np.allclose(
            np.nan_to_num(a.reconstruction.points), np.nan_to_num(b.reconstruction.points)
        )


class TestGraphTopology:
    """The comparison this whole exercise is about."""

    def test_full_graph_reconstructs_more_than_a_star(self, scene):
        pytest.importorskip("cv2")
        star_m = _verify(_star_pairs(scene, noise=0.5, outlier_ratio=0.15))
        full_m = _verify(_all_pairs(scene, noise=0.5, outlier_ratio=0.15))

        star = reconstruct(star_m, scene.K, build_tracks(star_m), ReconstructionConfig(seed=0))
        full = reconstruct(full_m, scene.K, build_tracks(full_m), ReconstructionConfig(seed=0))

        # The star graph cannot see points the reference misses.
        assert full.reconstruction.n_points > star.reconstruction.n_points

        # And it has strictly fewer observations tying the cameras together.
        n_obs = lambda r: sum(t.length for t in r.tracks)  # noqa: E731
        assert n_obs(full) > n_obs(star)

    def test_star_tracks_all_involve_the_reference(self, scene):
        star_m = _verify(_star_pairs(scene, noise=0.5))
        ref = scene.images[0]
        assert all(ref in t.images() for t in build_tracks(star_m))


class TestDegenerate:
    def test_too_few_matches_raises_clearly(self, scene):
        m = scene.matches_for("cam00", "cam01")
        m.pairs = m.pairs[:5]
        with pytest.raises(RuntimeError, match="could not estimate F"):
            reconstruct([m], scene.K, build_tracks([m]), ReconstructionConfig(seed=0))
