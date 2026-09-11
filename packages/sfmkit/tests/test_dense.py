"""The dense stage: off by default, refused without CUDA, and real on a GPU."""

from pathlib import Path

import numpy as np
import pytest

from sfmkit.apps.cli import dense as dense_cmd
from sfmkit.apps.cli import run as run_cmd
from sfmkit.data.colmap import dense_available, run_dense

REPO = Path(__file__).resolve().parents[3]
EXAMPLE = REPO / "examples" / "valencia" / "cpu"


class _Args:
    def __init__(self, config, out):
        self.config, self.out = str(config), str(out)
        self.From = self.only = None
        self.skip_done = False
        self.trials = 1


def _config(tmp_path, enabled: bool) -> Path:
    body = (REPO / "configs" / "valencia" / "cpu.yaml").read_text().split("\ndense:")[0]
    path = tmp_path / "exp.yaml"
    path.write_text(body + f"\ndense:\n  enabled: {str(enabled).lower()}\n")
    return path


@pytest.fixture
def in_repo(monkeypatch):
    monkeypatch.chdir(REPO)  # the config names the dataset under ./data


def test_off_by_default_it_does_nothing(tmp_path, in_repo):
    assert dense_cmd.cmd_dense(_Args(_config(tmp_path, False), tmp_path / "run")) == 0
    assert not (tmp_path / "run" / "dense").exists()


def test_without_cuda_the_stage_refuses(tmp_path, in_repo, monkeypatch):
    monkeypatch.setattr(dense_cmd, "dense_available", lambda: False)
    assert dense_cmd.cmd_dense(_Args(_config(tmp_path, True), tmp_path / "run")) == 1


def test_without_cuda_run_stops_before_the_first_stage(tmp_path, in_repo, monkeypatch):
    """Better than finding out after minutes of reconstruction."""
    ran = []
    monkeypatch.setattr(run_cmd, "STAGES",
                        [(n, lambda a, n=n: (ran.append(n), 0)[1]) for n, _ in run_cmd.STAGES])
    monkeypatch.setattr(run_cmd, "dense_available", lambda: False)
    assert run_cmd.cmd_run(_Args(_config(tmp_path, True), tmp_path / "run")) == 1
    assert ran == []
    assert run_cmd.cmd_run(_Args(_config(tmp_path, False), tmp_path / "run")) == 0


@pytest.mark.slow
@pytest.mark.skipif(not dense_available(), reason="needs pycolmap built with CUDA")
def test_a_dense_cloud_from_the_example_model(tmp_path):
    images = ["Img02", "Img25", "Img13", "Img14"]
    s = run_dense(EXAMPLE / "colmap", REPO / "data" / "valencia" / "scene", images, tmp_path,
                  max_image_size=600)
    assert s.n_images == len(images)  # the old photo, also in the model, is left out
    assert s.n_points > 1000
    assert (tmp_path / "fused.ply").stat().st_size > 0


class TestReadFused:
    """COLMAP's dense cloud, as it writes it: binary, with normals and colours."""

    def _ply(self, path, n=5, *, header=None, colours=True):
        import struct

        properties = ["property float x", "property float y", "property float z",
                      "property float nx", "property float ny", "property float nz"]
        if colours:
            properties += ["property uchar red", "property uchar green", "property uchar blue"]
        lines = header or ["ply", "format binary_little_endian 1.0", f"element vertex {n}",
                           *properties, "end_header"]
        body = b"".join(
            struct.pack("<6fBBB", i, 2.0 * i, 3.0 * i, 0.0, 0.0, 1.0, i, 10 + i, 20 + i)
            if colours else struct.pack("<6f", i, 2.0 * i, 3.0 * i, 0.0, 0.0, 1.0)
            for i in range(n))
        path.write_bytes(("\n".join(lines) + "\n").encode() + body)
        return path

    def test_the_points_and_their_colours_come_back(self, tmp_path):
        from sfmkit.data.colmap import read_fused

        points, colours = read_fused(self._ply(tmp_path / "fused.ply", 4))
        assert points.shape == (4, 3) and colours.shape == (4, 3)
        assert np.allclose(points[2], [2, 4, 6])
        assert colours.dtype == np.uint8 and list(colours[1]) == [1, 11, 21]

    def test_a_cloud_without_colours_is_refused(self, tmp_path):
        from sfmkit.data.colmap import read_fused

        with pytest.raises(ValueError, match="blue"):
            read_fused(self._ply(tmp_path / "grey.ply", 3, colours=False))

    def test_a_text_ply_is_refused_rather_than_guessed_at(self, tmp_path):
        from sfmkit.data.colmap import read_fused

        path = tmp_path / "text.ply"
        path.write_text("ply\nformat ascii 1.0\nelement vertex 1\n"
                        "property float x\nend_header\n0\n")
        with pytest.raises(ValueError, match="binary"):
            read_fused(path)


class TestRenderPoints:
    def test_points_land_where_the_camera_sees_them(self):
        from sfmkit.core.types import Pose
        from sfmkit.render.viz import render_points

        K = np.array([[100.0, 0, 50], [0, 100.0, 30], [0, 0, 1]])
        points = np.array([[0, 0, 10.0], [0, 0, 5.0], [0, 0, -1.0]])  # far, near, behind
        colours = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
        image = render_points(points, colours, K, Pose.identity(), (100, 60), spread=1)

        assert image.shape == (60, 100, 3)
        assert list(image[30, 50]) == [0, 255, 0]  # the nearer point covers the farther
        assert not (image == [0, 0, 255]).all(axis=2).any()  # the one behind is not drawn
        assert list(image[0, 0]) == [16, 16, 16]  # and the rest is background

    def test_the_orbit_keeps_looking_at_the_cloud(self):
        from sfmkit.core.geometry import project
        from sfmkit.core.types import Pose
        from sfmkit.render.viz import orbit

        points = np.random.default_rng(0).normal(0, 1, (200, 3)) + [0, 0, 10]
        K = np.array([[100.0, 0, 50], [0, 100.0, 50], [0, 0, 1]])
        swung = orbit(Pose.identity(), points, 40)

        middle = project(np.median(points, axis=0)[None], K, swung)[0]
        # the cloud's middle stays in the middle of the view, as far off as it was
        assert np.allclose(middle, [50, 50], atol=1e-6)
        assert np.isclose(np.linalg.norm(swung.center - np.median(points, axis=0)),
                          np.linalg.norm(np.median(points, axis=0)))
