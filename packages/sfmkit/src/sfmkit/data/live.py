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
from pathlib import Path
from typing import Protocol

import numpy as np
import redis

from sfmkit.core.reconstruct import Snapshot

VERSION = 1
BROKER_ENV = "SFMKIT_BROKER"
MAXLEN = 1000  # entries a stream keeps: far more than a run's steps
MAX_STEP_POINTS = 20_000  # points a step carries; beyond that it carries a sample
# How long a finished run's stream lives. It is kept at all so that a timeline
# can still be rewound after the fact; a week of that is generous, and without
# an expiry a broker that sees many runs only ever grows.
FINISHED_TTL = 7 * 24 * 60 * 60
ALIVE_SECONDS = 15  # how long the alive key outlives its last renewal
RENEW_SECONDS = 5


def name_of(run_dir) -> str:
    """How the viewer names this run: ``<project>/<config>``.

    A run lives at ``<projects>/<project>/runs/<config>/``, so the project is
    two levels up and not one. Getting it wrong publishes to a key nobody is
    listening on, and a run watched live shows nothing at all while writing its
    files perfectly, which is the hardest kind of wrong to notice.
    """
    run_dir = Path(run_dir)
    return f"{run_dir.parents[1].name}/{run_dir.name}"


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


def step_message(run: str, snapshot: Snapshot, limit: int = MAX_STEP_POINTS) -> dict:
    r = snapshot.report
    return {
        "v": VERSION, "kind": "step", "run": run,
        "step": int(r.step), "image": r.image,
        "n_registered": int(r.n_registered), "n_points": int(r.n_points),
        "rmse_before": _number(r.rmse_before), "rmse_after": _number(r.rmse_after),
        "bundle_seconds": float(r.bundle_seconds),
        "cameras": [{"name": n, "R": _matrix(p.R), "t": _vector(p.t)}
                    for n, p in snapshot.poses.items()],
        "points": _points(snapshot.points, limit),
    }


def end_message(run: str, n_cameras: int, n_points: int) -> dict:
    return {"v": VERSION, "kind": "end", "run": run, "n_cameras": int(n_cameras),
            "n_points": int(n_points)}


def stage_message(run: str, stage: str, state: str, seconds: float | None = None,
                  note: str | None = None) -> dict:
    """A stage of a whole run beginning, finishing, or stopping it.

    Only ``reconstruct`` has anything to say while it works; the rest are silent
    for minutes at a time, and a page watching a run should not have to guess
    whether it is matching or dead.
    """
    return {"v": VERSION, "kind": "stage", "run": run, "stage": stage, "state": state,
            "seconds": None if seconds is None else round(float(seconds), 1), "note": note}


def failed_message(run: str, error: BaseException) -> dict:
    """The run stopped short: an error, or the user interrupting it."""
    reason = f"{type(error).__name__}: {error}" if str(error) else type(error).__name__
    return {"v": VERSION, "kind": "failed", "run": run, "error": reason}


#: Streams this process has already opened, so only the first message of a run
#: empties one. Per process: a run is one process, whatever stages it does.
_opened: set[str] = set()

#: How many heartbeats are held on each key, so nested ones do not cut it short.
_held: dict[str, int] = {}
_held_lock = threading.Lock()


class Publisher(Protocol):
    def publish(self, message: dict) -> None: ...


class NullPublisher:
    """Publishes nothing: no broker configured."""

    def publish(self, message: dict) -> None:
        pass


class RedisPublisher:
    """Appends messages to a run's stream.

    A ``start`` empties the stream first, so a run repeated does not follow the
    steps of the last one, and an ``end`` or a ``failed`` starts its clock: the
    stream outlives the run by ``ttl`` seconds and is then Redis's to reclaim.
    """

    def __init__(self, client, run: str, on_error: Callable[[Exception], None] | None = None,
                 maxlen: int = MAXLEN, ttl: int = FINISHED_TTL) -> None:
        self.client = client
        self.key = stream_key(run)
        self.on_error = on_error
        self.maxlen = maxlen
        self.ttl = ttl
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
            # allow_nan=False: a NaN would break every reader's JSON. Encoded
            # before anything is touched, so a message that cannot be sent
            # cannot empty a stream either.
            data = json.dumps(message, allow_nan=False)
            # The first message of a run replaces what the last one left, so a
            # repeat does not follow its predecessor's steps. It is the first
            # and not the `start` because a whole run speaks before the
            # reconstruction does, and those stages would be wiped mid-run.
            if self.key not in _opened:
                _opened.add(self.key)
                self.client.delete(self.key)
            self.client.xadd(self.key, {"data": data}, maxlen=self.maxlen, approximate=True)
            if message["kind"] in ("end", "failed"):
                self.client.expire(self.key, self.ttl)
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

    They nest: `sfmkit run` holds one for the whole run and `reconstruct` holds
    its own, and the key goes when the last of them leaves. Without the count,
    the inner one leaving would delete the key mid-run and the run would look
    dead until the outer one renewed it.
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
        with _held_lock:
            _held[self.key] = _held.get(self.key, 0) + 1
        self._beat()
        self._thread = threading.Thread(target=self._loop, name="sfmkit-heartbeat", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join()
        with _held_lock:
            _held[self.key] -= 1
            last = _held[self.key] <= 0
            if last:
                del _held[self.key]
        if last:
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


def _points(points, limit: int) -> list[float]:
    """The model's points, flat, thinned to at most ``limit`` of them.

    A step carries the whole model rather than what changed, which is what lets
    a viewer draw any step without replaying the ones before it -- but it grows
    with steps times points, and all of it sits in the broker's memory. Valencia
    is 2 830 points and never reaches the limit; a few hundred cameras and 100k
    points would put hundreds of MB there without one. The sample is a stride
    through the array, so it covers the whole model rather than a corner of it,
    and ``n_points`` still reports how many there really are.
    """
    xyz = np.asarray(points).reshape(-1, 3)
    if limit and len(xyz) > limit:
        xyz = xyz[::-(-len(xyz) // limit)]
    return [round(float(v), 5) for v in xyz.ravel()]


def _vector(v) -> list[float]:
    return [float(x) for x in np.asarray(v).ravel()]


def _matrix(M) -> list[list[float]]:
    return [[float(x) for x in row] for row in np.asarray(M)]
