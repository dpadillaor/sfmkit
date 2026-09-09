"""Execute every Python block in docs/tour.md.

A tour whose code does not run is worse than no tour. This extracts the blocks
in order and runs them in one shared namespace, exactly as a reader pasting
them into a session would, so the documentation cannot drift away from the API
without the suite noticing.
"""

import re
from pathlib import Path

import pytest

TOUR = Path(__file__).resolve().parent.parent / "docs" / "tour.md"


def _python_blocks(text: str) -> list[str]:
    blocks = re.findall(r"```python\n(.*?)```", text, re.S)
    # Lines that are bare expressions with a trailing "# value" comment are shown
    # as REPL output in the prose; they are valid statements and run fine.
    return blocks


@pytest.mark.skipif(not TOUR.is_file(), reason="tour not present")
def test_every_block_in_the_tour_runs():
    blocks = _python_blocks(TOUR.read_text())
    assert len(blocks) >= 8, f"expected the tour's blocks, found {len(blocks)}"

    namespace: dict = {}
    for i, block in enumerate(blocks):
        # The final block is an excerpt from the test suite, shown as an example
        # of executable documentation rather than as a step to run.
        if block.lstrip().startswith("def test_"):
            continue
        try:
            exec(compile(block, f"<tour block {i}>", "exec"), namespace)
        except Exception as e:  # noqa: BLE001 - the point is to report which block
            pytest.fail(f"block {i} of docs/tour.md failed: {type(e).__name__}: {e}\n\n{block}")
