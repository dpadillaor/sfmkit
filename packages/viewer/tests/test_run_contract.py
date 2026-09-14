"""What the viewer reads is what the contract says it will be given.

The other half is in sfmkit's suite, where what it writes is held to the same
file. Between them a renamed array fails on both sides the day it is renamed,
instead of on the day someone runs the pipeline and finds an empty page.

The fixtures matter as much as the frozen run: they are what every other test
here is written against, so if they drift from the format sfmkit writes, this
suite would go on passing while the viewer stopped working.
"""

from pathlib import Path

import pytest

from sfmcontracts import run
from synthetic import make_run

PROJECTS = Path(__file__).resolve().parents[3] / "projects"
FROZEN = sorted(PROJECTS.glob("*/runs/reference-*"))


def test_the_fixtures_are_what_sfmkit_would_have_written(tmp_path):
    made = make_run(tmp_path, "city", "full", dense=True, query="Img00")
    assert run.errors(made) == []


@pytest.mark.skipif(not FROZEN, reason="no frozen run")
@pytest.mark.parametrize("frozen", FROZEN, ids=lambda p: p.name)
def test_a_frozen_run_keeps_to_the_contract(frozen):
    assert run.errors(frozen) == []
