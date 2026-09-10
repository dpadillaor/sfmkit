"""Change detection: homography alignment and structural comparison."""

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from sfmkit.core.changes import align_by_homography, detect_changes  # noqa: E402


def _textured_image(seed=0, size=(400, 600)):
    """A deterministic image with enough structure for a homography to lock onto."""
    rng = np.random.default_rng(seed)
    img = rng.integers(60, 200, size, dtype=np.uint8)
    img = cv2.GaussianBlur(img, (0, 0), 2)
    for _ in range(40):
        x, y = rng.integers(20, size[1] - 40), rng.integers(20, size[0] - 40)
        cv2.rectangle(img, (x, y), (x + 25, y + 25), int(rng.integers(0, 255)), -1)
    return img


def _grid_correspondences(H, size=(400, 600), step=40):
    ys, xs = np.mgrid[step:size[0]:step, step:size[1]:step]
    src = np.column_stack([xs.ravel(), ys.ravel()]).astype(float)
    dst = cv2.perspectiveTransform(src.reshape(-1, 1, 2), H).reshape(-1, 2)
    return src, dst


class TestHomography:
    def test_recovers_a_known_transform(self):
        H_true = np.array([[1.02, 0.03, 12.0], [-0.02, 0.99, -7.0], [1e-5, 2e-6, 1.0]])
        src, dst = _grid_correspondences(H_true)
        H, inliers = align_by_homography(src, dst, seed=0)
        assert inliers.all()
        H = H / H[2, 2]
        back = cv2.perspectiveTransform(src.reshape(-1, 1, 2), H).reshape(-1, 2)
        assert np.abs(back - dst).max() < 1e-3

    def test_survives_outliers(self):
        H_true = np.array([[1.0, 0.0, 20.0], [0.0, 1.0, -10.0], [0.0, 0.0, 1.0]])
        src, dst = _grid_correspondences(H_true)
        rng = np.random.default_rng(0)
        bad = rng.choice(len(src), len(src) // 5, replace=False)
        dst[bad] += rng.normal(0, 150, (len(bad), 2))
        _, inliers = align_by_homography(src, dst, seed=0)
        assert not inliers[bad].any()

    def test_degenerate_input_raises(self):
        pts = np.zeros((6, 2))
        with pytest.raises((ValueError, cv2.error)):
            align_by_homography(pts, pts, seed=0)


class TestDetectChanges:
    def test_identical_images_report_almost_no_change(self):
        img = _textured_image(0)
        H = np.eye(3)
        src, dst = _grid_correspondences(H)
        result = detect_changes(img, img, src, dst, seed=0)
        assert result.changed_fraction < 0.02

    def test_invariant_to_global_brightness_and_contrast(self):
        """A century-old plate differs in exposure everywhere; that is not change."""
        img = _textured_image(1)
        altered = np.clip(img.astype(float) * 0.55 + 60, 0, 255).astype(np.uint8)
        src, dst = _grid_correspondences(np.eye(3))
        result = detect_changes(img, altered, src, dst, seed=0)
        assert result.changed_fraction < 0.05

    def test_finds_an_inserted_object(self):
        img = _textured_image(2)
        modified = img.copy()
        cv2.rectangle(modified, (250, 150), (380, 280), 0, -1)
        src, dst = _grid_correspondences(np.eye(3))
        result = detect_changes(img, modified, src, dst, seed=0)
        assert result.changed_fraction > 0.02
        # The flagged region should overlap where the object was inserted.
        assert result.mask[150:280, 250:380].mean() > 0.3

    def test_the_difference_image_is_dark_where_the_images_agree(self):
        img = _textured_image(4)
        modified = img.copy()
        cv2.rectangle(modified, (250, 150), (380, 280), 0, -1)
        src, dst = _grid_correspondences(np.eye(3))
        result = detect_changes(img, modified, src, dst, seed=0)
        assert result.difference.shape == img.shape
        assert result.difference[20:120, 20:200].mean() < 2  # unchanged: near black
        assert result.difference[160:270, 260:370].mean() > 40  # the inserted object

    def test_reports_the_homography_and_inliers(self):
        img = _textured_image(3)
        src, dst = _grid_correspondences(np.eye(3))
        result = detect_changes(img, img, src, dst, seed=0)
        assert result.homography.shape == (3, 3)
        assert result.n_inliers > 0
        assert result.warped.shape == img.shape
        assert result.mask.dtype == bool
