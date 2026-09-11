"""The dense stage: off by default, refused without CUDA, and real on a GPU."""

from pathlib import Path

import pytest

from sfmkit.apps.cli import dense as dense_cmd
from sfmkit.apps.cli import run as run_cmd
from sfmkit.data.colmap import dense_available, run_dense

REPO = Path(__file__).resolve().parents[3]
EXAMPLE = REPO / "examples" / "valencia" / "9cameras"


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
