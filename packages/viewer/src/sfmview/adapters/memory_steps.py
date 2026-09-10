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

    def publish(self, run: RunId, message: Mapping) -> None:
        self._runs[str(run)].append(message)

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
