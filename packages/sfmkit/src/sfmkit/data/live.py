"""Live progress, published to a broker for whoever is watching: the viewer.

The messages follow ``contracts/step.schema.json``: a ``start``, a ``step`` after
each camera registered or refinement, an ``end``. They go to a Redis stream,
one per run, which keeps them, so a viewer that arrives late still sees every
step. Publishing never stops a run: when the broker cannot be reached, the
publisher says so once and drops what follows.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Callable
from typing import Protocol

import numpy as np
import redis

from sfmkit.core.reconstruct import Snapshot

VERSION = 1
BROKER_ENV = "SFMKIT_BROKER"
MAXLEN = 1000  # entries a stream keeps: far more than a run's steps


def stream_key(run: str) -> str:
    """The Redis stream of a run, ``<project>/<config>``."""
    return f"sfmkit:steps:{run}"


def start_message(run: str, K: np.ndarray, images: list[str]) -> dict:
    return {"v": VERSION, "kind": "start", "run": run, "K": _matrix(K), "images": list(images)}


def step_message(run: str, snapshot: Snapshot) -> dict:
    r = snapshot.report
    return {
        "v": VERSION, "kind": "step", "run": run,
        "step": int(r.step), "image": r.image,
        "n_registered": int(r.n_registered), "n_points": int(r.n_points),
        "rmse_before": _number(r.rmse_before), "rmse_after": _number(r.rmse_after),
        "bundle_seconds": float(r.bundle_seconds),
        "cameras": [{"name": n, "R": _matrix(p.R), "t": _vector(p.t)}
                    for n, p in snapshot.poses.items()],
        "points": [round(float(v), 5) for v in np.asarray(snapshot.points).ravel()],
    }


def end_message(run: str, n_cameras: int, n_points: int) -> dict:
    return {"v": VERSION, "kind": "end", "run": run, "n_cameras": int(n_cameras),
            "n_points": int(n_points)}


class Publisher(Protocol):
    def publish(self, message: dict) -> None: ...


class NullPublisher:
    """Publishes nothing: no broker configured."""

    def publish(self, message: dict) -> None:
        pass


class RedisPublisher:
    """Appends messages to a run's stream. A ``start`` empties the stream first,
    so a run repeated does not follow the steps of the last one."""

    def __init__(self, client, run: str, on_error: Callable[[Exception], None] | None = None,
                 maxlen: int = MAXLEN) -> None:
        self.client = client
        self.key = stream_key(run)
        self.on_error = on_error
        self.maxlen = maxlen
        self.failed = False

    @classmethod
    def from_url(cls, url: str, run: str, **kw) -> RedisPublisher:
        # Short timeouts: a missing broker must cost a run seconds, not minutes.
        client = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        return cls(client, run, **kw)

    def publish(self, message: dict) -> None:
        if self.failed:
            return
        try:
            if message["kind"] == "start":
                self.client.delete(self.key)
            self.client.xadd(self.key, {"data": json.dumps(message)},
                             maxlen=self.maxlen, approximate=True)
        except Exception as e:  # the broker's trouble is never the run's
            self.failed = True
            if self.on_error is not None:
                self.on_error(e)


def publisher(run: str, on_error: Callable[[Exception], None] | None = None) -> Publisher:
    """A publisher for ``run`` to the broker in ``SFMKIT_BROKER``, if one is set."""
    url = os.environ.get(BROKER_ENV)
    if not url:
        return NullPublisher()
    return RedisPublisher.from_url(url, run, on_error=on_error)


def _number(x: float) -> float | None:
    x = float(x)
    return x if math.isfinite(x) else None  # JSON has no NaN


def _vector(v) -> list[float]:
    return [float(x) for x in np.asarray(v).ravel()]


def _matrix(M) -> list[list[float]]:
    return [[float(x) for x in row] for row in np.asarray(M)]
