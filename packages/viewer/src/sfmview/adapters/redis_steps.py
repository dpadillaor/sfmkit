"""A ``StepSource`` over Redis Streams, where sfmkit publishes.

One stream per run, ``sfmkit:steps:<project>/<config>``, one message per entry
in its ``data`` field (``contracts/step.schema.json``). A blocking ``XREAD`` waits
for new entries without holding the server up.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import redis.asyncio as redis
from redis.exceptions import RedisError

from sfmview.domain import LiveEvent, RunId

PREFIX = "sfmkit:steps:"


def stream_key(run: RunId) -> str:
    return f"{PREFIX}{run}"


class RedisStepSource:
    """Reads runs' streams. When Redis cannot be reached it tries again every
    ``retry`` seconds, so a viewer started before the broker catches up."""

    def __init__(self, client: redis.Redis, block_ms: int = 5000, retry: float = 2.0) -> None:
        self.client = client
        self.block_ms = block_ms
        self.retry = retry

    @classmethod
    def from_url(cls, url: str, **kw) -> RedisStepSource:
        return cls(redis.Redis.from_url(url, socket_connect_timeout=2), **kw)

    async def events(self, run: RunId, after: str = "0") -> AsyncIterator[LiveEvent]:
        key, last = stream_key(run), after
        while True:
            try:
                reply = await self.client.xread({key: last}, count=100, block=self.block_ms)
            except (RedisError, OSError):
                await asyncio.sleep(self.retry)
                continue
            for _, entries in reply or []:
                for entry_id, fields in entries:
                    last = entry_id.decode() if isinstance(entry_id, bytes) else entry_id
                    try:
                        message = json.loads(fields[b"data"])
                    except (KeyError, ValueError):
                        continue  # not a message of ours
                    yield LiveEvent(last, message)

    async def ping(self) -> bool:
        try:
            return bool(await self.client.ping())
        except (RedisError, OSError):
            return False
