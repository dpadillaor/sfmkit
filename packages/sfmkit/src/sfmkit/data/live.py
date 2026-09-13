"""Live progress, published to a broker for whoever is watching: the viewer.

The messages follow ``contracts/step.schema.json``: a ``start``, a ``step`` after
each camera registered or refinement, an ``end``, or ``failed``. They go to a Redis stream,
one per run, which keeps them, so a viewer that arrives late still sees every
step. Publishing never stops a run: when the broker cannot be reached, the
publisher says so once and drops what follows.

While the run works, a heartbeat keeps a key alive beside the stream, so a
watcher can tell a run still at work from one that died without a word.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import threading
from collections.abc import Callable
from typing import Protocol

import numpy as np
import redis

from sfmkit.core.reconstruct import Snapshot

VERSION = 1
BROKER_ENV = "SFMKIT_BROKER"
MAXLEN = 1000  # entries a stream keeps: far more than a run's steps
ALIVE_SECONDS = 15  # how long the alive key outlives its last renewal
RENEW_SECONDS = 5


def stream_key(run: str) -> str:
    """The Redis stream of a run, ``<project>/<config>``."""
    return f"sfmkit:steps:{run}"


def alive_key(run: str) -> str:
    """The key that exists while a run is at work."""
    return f"sfmkit:alive:{run}"


def start_message(run: str, K: np.ndarray, images: list[str],
                  reference: str | None = None) -> dict:
    """The run opening. ``reference`` lets a watcher draw the steps in the frame
    the finished model will use, rather than in the seed pair's."""
    return {"v": VERSION, "kind": "start", "run": run, "K": _matrix(K),
            "images": list(images), "reference": reference}


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


def failed_message(run: str, error: BaseException) -> dict:
    """The run stopped short: an error, or the user interrupting it."""
    reason = f"{type(error).__name__}: {error}" if str(error) else type(error).__name__
    return {"v": VERSION, "kind": "failed", "run": run, "error": reason}


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
            # allow_nan=False: a NaN would break every reader's JSON.
            self.client.xadd(self.key, {"data": json.dumps(message, allow_nan=False)},
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


class Heartbeat:
    """Keeps ``alive_key(run)`` set while the ``with`` block runs: for ``ttl``
    seconds, renewed every ``every`` from a thread, deleted on the way out.

    A run killed outright stops renewing it and Redis lets it expire. Unlike the
    publisher it never gives up, so a broker back mid-run hears from it again.
    """

    def __init__(self, client, run: str, ttl: float = ALIVE_SECONDS,
                 every: float = RENEW_SECONDS) -> None:
        self.client = client
        self.key = alive_key(run)
        self.ttl = ttl
        self.every = every
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> Heartbeat:
        self._beat()
        self._thread = threading.Thread(target=self._loop, name="sfmkit-heartbeat", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join()
        with contextlib.suppress(Exception):
            self.client.delete(self.key)

    def _loop(self) -> None:
        while not self._stop.wait(self.every):
            self._beat()

    def _beat(self) -> None:
        with contextlib.suppress(Exception):  # the broker's trouble is never the run's
            self.client.set(self.key, "1", px=int(self.ttl * 1000))


def heartbeat(run: str) -> contextlib.AbstractContextManager:
    """A ``Heartbeat`` for ``run`` on the broker in ``SFMKIT_BROKER``, if one is set."""
    url = os.environ.get(BROKER_ENV)
    if not url:
        return contextlib.nullcontext()
    client = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
    return Heartbeat(client, run)


def _number(x: float) -> float | None:
    x = float(x)
    return x if math.isfinite(x) else None  # JSON has no NaN


def _vector(v) -> list[float]:
    return [float(x) for x in np.asarray(v).ravel()]


def _matrix(M) -> list[list[float]]:
    return [[float(x) for x in row] for row in np.asarray(M)]
