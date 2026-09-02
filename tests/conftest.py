import numpy as np
import pytest

from sfmkit.synthetic import make_scene


@pytest.fixture(scope="session")
def scene():
    """A 5-camera synthetic scene shared across tests."""
    return make_scene(n_cameras=5, n_points=300, seed=0)


@pytest.fixture(scope="session")
def noisy_matches(scene):
    """All pairs of the scene, with sub-pixel noise and 20% outliers."""
    out = []
    for i, a in enumerate(scene.images):
        for b in scene.images[i + 1:]:
            m = scene.matches_for(a, b, noise=0.5, outlier_ratio=0.2, seed=hash((a, b)) % 2**31)
            if m.n_matches >= 20:
                out.append(m)
    return out


@pytest.fixture
def rng():
    return np.random.default_rng(0)
