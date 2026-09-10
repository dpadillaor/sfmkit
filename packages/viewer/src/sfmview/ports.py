"""What the viewer needs from the outside world, as interfaces.

The API depends on these and on nothing concrete; ``main`` picks the adapters.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol

from sfmview.domain import LiveEvent, RunId, RunSummary, Scene


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


class StepSource(Protocol):
    """Runs' live progress, as sfmkit publishes it."""

    def events(self, run: RunId, after: str = "0") -> AsyncIterator[LiveEvent]:
        """The run's messages after ``after`` ("0": from the first), then each
        new one as it comes. It never ends; the caller stops listening."""
        ...

    async def ping(self) -> bool:
        """Whether the source can be reached."""
        ...
