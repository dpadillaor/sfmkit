"""The TUI's data layer. Deliberately importable without Textual installed."""

import json

import pytest

from sfmkit.apps.tui.model import RunSummary, compare, load_runs


def _write_run(root, name, stages: dict):
    d = root / name
    for stage, payload in stages.items():
        (d / stage).mkdir(parents=True)
        (d / stage / "manifest.json").write_text(json.dumps(payload))
    return d


@pytest.fixture
def runs_dir(tmp_path):
    _write_run(tmp_path, "alpha", {
        "reconstruct": {"timestamp": "2026-09-02T01:00:00", "git_commit": "abc12345",
                        "config": {"name": "star"}, "n_cameras": 4, "n_points": 675,
                        "tracks": {"n_tracks": 900, "mean_length": 2.0}},
        "evaluate": {"timestamp": "2026-09-02T01:05:00",
                     "mean_rotation_error_deg": 0.96, "scale": 0.44},
    })
    _write_run(tmp_path, "beta", {
        "reconstruct": {"timestamp": "2026-09-02T02:00:00", "git_commit": "def67890",
                        "config": {"name": "complete"}, "n_cameras": 9, "n_points": 1404,
                        "tracks": {"n_tracks": 2104, "mean_length": 3.3}},
    })
    (tmp_path / "not-a-run").mkdir()
    return tmp_path


class TestLoadRuns:
    def test_finds_runs_and_orders_newest_first(self, runs_dir):
        runs = load_runs(runs_dir)
        assert [r.name for r in runs] == ["beta", "alpha"]

    def test_ignores_directories_without_manifests(self, runs_dir):
        assert "not-a-run" not in [r.name for r in load_runs(runs_dir)]

    def test_nested_runs_are_named_by_their_relative_path(self, tmp_path):
        _write_run(tmp_path, "valencia/all9", {"match": {"timestamp": "2026-09-10T01:00:00"}})
        assert [r.name for r in load_runs(tmp_path)] == ["valencia/all9"]

    def test_folders_that_are_not_stages_are_ignored(self, tmp_path):
        _write_run(tmp_path, "r", {"scratch": {"timestamp": "2026-09-10T01:00:00"}})
        assert load_runs(tmp_path) == []

    def test_missing_root_is_not_an_error(self, tmp_path):
        assert load_runs(tmp_path / "nope") == []

    def test_survives_a_corrupt_manifest(self, tmp_path):
        d = tmp_path / "broken" / "reconstruct"
        d.mkdir(parents=True)
        (d / "manifest.json").write_text("{not json")
        assert load_runs(tmp_path) == []


class TestSummary:
    def test_reports_completed_stages(self, runs_dir):
        alpha = next(r for r in load_runs(runs_dir) if r.name == "alpha")
        assert alpha.completed == ["reconstruct", "evaluate"]

    def test_headline_pulls_across_stages(self, runs_dir):
        alpha = next(r for r in load_runs(runs_dir) if r.name == "alpha")
        h = alpha.headline
        assert h["cameras"] == 4
        assert h["mean_rot"] == 0.96  # from evaluate, not reconstruct
        assert h["tracks"] == 900

    def test_missing_metrics_do_not_raise(self, runs_dir):
        beta = next(r for r in load_runs(runs_dir) if r.name == "beta")
        assert beta.headline["mean_rot"] is None
        assert beta.metric("nothing", "here", default="-") == "-"

    def test_empty_run_is_harmless(self):
        r = RunSummary(path=None, name="x")
        assert r.completed == [] and r.config_name == "-" and r.timestamp == "-"


class TestCompare:
    def test_produces_a_row_per_field(self, runs_dir):
        runs = load_runs(runs_dir)
        rows = compare(runs[0], runs[1])
        assert all(len(r) == 3 for r in rows)
        labels = [r[0] for r in rows]
        assert "cameras" in labels and "mean rot err (deg)" in labels

    def test_shows_both_values(self, runs_dir):
        runs = {r.name: r for r in load_runs(runs_dir)}
        rows = dict((r[0], (r[1], r[2])) for r in compare(runs["alpha"], runs["beta"]))
        assert rows["cameras"] == ("4", "9")
        assert rows["3D points"] == ("675", "1404")


class TestConfigPath:
    """The TUI needs to know which config produced a run in order to re-run it."""

    def test_reads_the_recorded_path(self, tmp_path):
        _write_run(tmp_path, "r", {"reconstruct": {
            "timestamp": "2026-09-02T01:00:00",
            "config_path": "configs/whatever.yaml",
            "config": {"name": "whatever"},
        }})
        assert load_runs(tmp_path)[0].config_path == "configs/whatever.yaml"

    def test_returns_none_when_unrecorded_and_unguessable(self, runs_dir):
        # These fixtures predate config_path, so there is nothing to report.
        alpha = next(r for r in load_runs(runs_dir) if r.name == "alpha")
        assert alpha.config_path is None
