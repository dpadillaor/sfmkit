"""The interface itself, driven headless: it must lay out and show the runs."""

import asyncio
import json

import pytest

pytest.importorskip("textual")

from sfmkit.apps.tui.app import CompareView, RunList, SfmkitApp, StageDetail  # noqa: E402


@pytest.fixture
def runs_dir(tmp_path):
    for name, cams in (("valencia/9cameras", 9), ("valencia/star", 8)):
        stage = tmp_path / name / "reconstruct"
        stage.mkdir(parents=True)
        (stage / "manifest.json").write_text(json.dumps({
            "timestamp": "2026-09-10T10:00:00", "config": {"name": name.split("/")[1]},
            "n_cameras": cams, "n_points": 1000,
        }))
    return tmp_path


def test_every_panel_gets_room_on_screen(runs_dir):
    """A panel of height zero draws nothing: the runs tab once came up blank."""
    async def check():
        app = SfmkitApp(runs_dir)
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.pause()
            runs, detail = app.query_one(RunList), app.query_one(StageDetail)
            assert runs.row_count == 2
            assert runs.size.height >= 3 and detail.size.height >= 10
            app.query_one("TabbedContent").active = "tab-compare"
            await pilot.pause()
            assert app.query_one(CompareView).size.height > 0

    asyncio.run(check())


def test_marking_two_runs_fills_the_comparison(runs_dir):
    async def check():
        app = SfmkitApp(runs_dir)
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.press("a", "down", "b")
            header = [str(c) for c in app.query_one(CompareView).get_row_at(0)]
            assert "valencia/9cameras" in header[1] + header[2]
            assert "valencia/star" in header[1] + header[2]

    asyncio.run(check())
