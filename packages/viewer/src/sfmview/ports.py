"""What the viewer needs from the outside world, as interfaces.

The API depends on these and on nothing concrete; ``main`` picks the adapters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from sfmview.domain import RunId, RunSummary, Scene


class RunStore(Protocol):
    """Finished runs: what they hold, and their results."""

    def runs(self) -> list[RunSummary]:
        """Every run, newest first."""
        ...

    def scene(self, run: RunId) -> Scene:
        """The run's models in one frame. Raises ``RunNotFound``."""
        ...

    def dense_file(self, run: RunId) -> Path:
        """The run's dense cloud, a local PLY file. Raises ``RunNotFound``."""
        ...
