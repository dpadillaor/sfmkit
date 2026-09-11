"""A ``StepSource`` held in memory: for tests, and to try the page without a broker."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator, Mapping

from sfmview.domain import LiveEvent, RunId


class MemoryStepSource:
    """Messages kept per run, numbered from 1 as ``"<n>-0"``, like a stream's ids.

    ``publish`` may be called from any thread; readers look for new messages
    every ``poll`` seconds.
    """

    def __init__(self, poll: float = 0.02) -> None:
        self.poll = poll
        self._runs: dict[str, list[Mapping]] = defaultdict(list)
        self._alive: set[RunId] = set()

    def publish(self, run: RunId, message: Mapping) -> None:
        self._runs[str(run)].append(message)

    def beat(self, run: RunId, alive: bool = True) -> None:
        """Say ``run`` is at work, or no longer, as sfmkit's heartbeat would."""
        (self._alive.add if alive else self._alive.discard)(run)

    async def events(self, run: RunId, after: str = "0") -> AsyncIterator[LiveEvent]:
        messages = self._runs[str(run)]
        seen = int(after.split("-")[0])
        while True:
            while seen < len(messages):
                seen += 1
                yield LiveEvent(f"{seen}-0", messages[seen - 1])
            await asyncio.sleep(self.poll)

    async def ping(self) -> bool:
        return True

    async def running(self, runs: list[RunId]) -> set[RunId] | None:
        return {run for run in runs if run in self._alive}
