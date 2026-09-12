"""The `run` command's stage selection, without executing any stage."""

from pathlib import Path

import pytest

from sfmkit.apps.cli.run import STAGES, cmd_run

CONFIG = Path(__file__).resolve().parents[3] / "configs" / "valencia" / "cpu.yaml"


class _Args:
    def __init__(self, out, **kw):
        self.config = str(CONFIG)
        self.out = str(out)
        self.From = kw.get("From")
        self.only = kw.get("only")
        self.skip_done = kw.get("skip_done", False)
        self.trials = 1


@pytest.fixture
def ran(monkeypatch):
    """Replace every stage with a recorder, so nothing actually runs."""
    order = []
    patched = [(name, lambda a, n=name: (order.append(n), 0)[1]) for name, _ in STAGES]
    monkeypatch.setattr("sfmkit.apps.cli.run.STAGES", patched)
    return order


def test_runs_every_stage_in_order(ran, tmp_path):
    assert cmd_run(_Args(tmp_path)) == 0
    assert ran == [name for name, _ in STAGES]


def test_from_starts_partway(ran, tmp_path):
    assert cmd_run(_Args(tmp_path, From="reconstruct")) == 0
    assert ran[0] == "reconstruct"
    assert "match" not in ran


def test_only_selects_a_subset(ran, tmp_path):
    assert cmd_run(_Args(tmp_path, only="verify,evaluate")) == 0
    assert ran == ["verify", "evaluate"]


def test_only_rejects_unknown_stages(ran, tmp_path):
    assert cmd_run(_Args(tmp_path, only="verify,nonsense")) == 1
    assert ran == []


def test_skip_done_honours_existing_manifests(ran, tmp_path):
    for stage in ("calibrate", "match", "verify"):
        (tmp_path / stage).mkdir()
        (tmp_path / stage / "manifest.json").write_text("{}")
    assert cmd_run(_Args(tmp_path, skip_done=True)) == 0
    assert not {"calibrate", "match", "verify"} & set(ran)
    assert ran[0] == "reconstruct"


def test_stops_at_the_first_failure(monkeypatch, tmp_path):
    order = []

    def ok(a, n):
        order.append(n)
        return 0

    def fails(a, n):
        order.append(n)
        return 3

    patched = [("match", lambda a: ok(a, "match")),
               ("verify", lambda a: fails(a, "verify")),
               ("reconstruct", lambda a: ok(a, "reconstruct"))]
    monkeypatch.setattr("sfmkit.apps.cli.run.STAGES", patched)
    assert cmd_run(_Args(tmp_path)) == 3
    assert order == ["match", "verify"], "must not continue past a failure"


def test_run_help_lists_the_stages_in_order(capsys):
    """A newcomer cannot tell the order from `sfmkit --help`; here it is."""
    from sfmkit.apps.cli.main import build_parser

    with pytest.raises(SystemExit):
        build_parser().parse_args(["run", "--help"])
    printed = capsys.readouterr().out
    at = [printed.index(f"\n  {name:<12}") for name, _ in STAGES]
    assert at == sorted(at), "the stages are listed out of order"
    assert "calibrate   intrinsics" in printed  # each with what it does
