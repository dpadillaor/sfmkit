"""Live progress: the messages sfmkit publishes, and how it publishes them."""

import contextlib
import json
import os
import time

import numpy as np
import pytest
import redis

from contract import STEP_EXAMPLES, step_errors
from sfmkit.core.reconstruct import Snapshot, StageReport
from sfmkit.core.types import Pose
from sfmkit.data import live

RUN = "valencia/9cameras"


@pytest.fixture
def snapshot():
    report = StageReport(0, "Img12", 2, 2, 40, rmse_before=float("nan"), rmse_after=0.8,
                         bundle_seconds=1.5)
    poses = {"Img02": Pose(np.eye(3), np.zeros(3)), "Img12": Pose(np.eye(3), np.array([-1, 0, 0]))}
    return Snapshot(report, poses, np.array([[0.1, 0.2, 5.0], [-0.3, 0.1, 6.0]]))


def test_the_examples_keep_to_the_contract():
    for message in STEP_EXAMPLES:
        assert step_errors(message) == []


def test_our_messages_keep_to_the_contract(snapshot):
    K = np.array([[3544.0, 0, 2016], [0, 3544, 1134], [0, 0, 1]])
    for message in (live.start_message(RUN, K, ["Img02", "Img12"]),
                    live.step_message(RUN, snapshot),
                    live.end_message(RUN, 2, 2),
                    live.failed_message(RUN, KeyboardInterrupt()),
                    live.failed_message(RUN, RuntimeError("could not estimate F"))):
        assert step_errors(message) == [], message["kind"]


def test_a_step_carries_the_model_as_it_stood(snapshot):
    m = live.step_message(RUN, snapshot)
    assert m["rmse_before"] is None  # NaN, which JSON cannot carry
    assert m["points"] == [0.1, 0.2, 5.0, -0.3, 0.1, 6.0]
    assert [c["name"] for c in m["cameras"]] == ["Img02", "Img12"]
    assert m["cameras"][1]["t"] == [-1.0, 0.0, 0.0]


def test_a_failure_says_why():
    assert live.failed_message(RUN, KeyboardInterrupt())["error"] == "KeyboardInterrupt"
    assert live.failed_message(RUN, RuntimeError("no F"))["error"] == "RuntimeError: no F"


def test_the_contract_catches_what_is_wrong(snapshot):
    m = live.step_message(RUN, snapshot)
    assert step_errors({**m, "bundle_seconds": float("nan")})  # JSON has no NaN
    assert step_errors({**m, "v": 2})
    assert step_errors({k: v for k, v in m.items() if k != "points"})
    assert step_errors({**m, "extra": 1})
    bad = {**m, "cameras": [{"name": "Img02", "R": [[1, 0], [0, 1]], "t": [0, 0, 0]}]}
    assert step_errors(bad)


def test_a_message_that_is_not_json_is_refused_not_sent(snapshot):
    client, errors = FakeRedis(), []
    publisher = live.RedisPublisher(client, RUN, on_error=errors.append)
    publisher.publish({**live.step_message(RUN, snapshot), "bundle_seconds": float("nan")})
    assert client.calls == [] and isinstance(errors[0], ValueError)


@pytest.fixture(autouse=True)
def a_stream_never_opened():
    """Each test is a process that has published nothing yet: the first message
    of a run empties its stream, and that is remembered per process."""
    live._opened.clear()
    yield
    live._opened.clear()


class FakeRedis:
    def __init__(self, fail: bool = False) -> None:
        self.calls = []
        self.fail = fail

    def delete(self, key):
        self.calls.append(("delete", key))

    def set(self, key, value, px=None):
        if self.fail:
            raise redis.ConnectionError("no broker")
        self.calls.append(("set", key, px))

    def xadd(self, key, fields, maxlen=None, approximate=None):
        if self.fail:
            raise redis.ConnectionError("no broker")
        self.calls.append(("xadd", key, json.loads(fields["data"]), maxlen))


def test_the_first_message_empties_the_stream_then_everything_is_appended(snapshot):
    client = FakeRedis()
    publisher = live.RedisPublisher(client, RUN)
    publisher.publish(live.start_message(RUN, np.eye(3), []))
    publisher.publish(live.step_message(RUN, snapshot))
    key = "sfmkit:steps:valencia/9cameras"
    assert [c[:2] for c in client.calls] == [("delete", key), ("xadd", key), ("xadd", key)]
    assert client.calls[2][2]["kind"] == "step" and client.calls[2][3] == live.MAXLEN


def test_the_reconstruction_does_not_wipe_the_stages_before_it():
    """`sfmkit run` publishes stages before `reconstruct` says start; its own
    publisher must not throw those away."""
    client = FakeRedis()
    run_publisher = live.RedisPublisher(client, RUN)
    run_publisher.publish(live.stage_message(RUN, "match", "start"))
    reconstruct_publisher = live.RedisPublisher(client, RUN)  # the stage builds its own
    reconstruct_publisher.publish(live.start_message(RUN, np.eye(3), []))
    assert [c[0] for c in client.calls] == ["delete", "xadd", "xadd"]


def test_an_unreachable_broker_is_reported_once_and_never_stops_the_run(snapshot):
    errors = []
    publisher = live.RedisPublisher(FakeRedis(fail=True), RUN, on_error=errors.append)
    for _ in range(3):
        publisher.publish(live.step_message(RUN, snapshot))  # does not raise
    assert len(errors) == 1 and isinstance(errors[0], redis.ConnectionError)


def test_no_broker_configured_publishes_nothing(monkeypatch):
    monkeypatch.delenv(live.BROKER_ENV, raising=False)
    assert isinstance(live.publisher(RUN), live.NullPublisher)
    monkeypatch.setenv(live.BROKER_ENV, "redis://localhost:6379")
    assert isinstance(live.publisher(RUN), live.RedisPublisher)


def test_a_heartbeat_keeps_the_key_while_the_run_works_then_deletes_it():
    client = FakeRedis()
    with live.Heartbeat(client, RUN, ttl=0.3, every=0.02):
        time.sleep(0.15)
    key = "sfmkit:alive:valencia/9cameras"
    assert client.calls[0] == ("set", key, 300) and client.calls[-1] == ("delete", key)
    assert sum(c[0] == "set" for c in client.calls) >= 3  # renewed, not set once


def test_a_heartbeat_never_stops_the_run():
    with live.Heartbeat(FakeRedis(fail=True), RUN, every=0.01):
        time.sleep(0.05)  # beats that fail, silently


def test_no_broker_configured_no_heartbeat(monkeypatch):
    monkeypatch.delenv(live.BROKER_ENV, raising=False)
    assert isinstance(live.heartbeat(RUN), contextlib.nullcontext)
    monkeypatch.setenv(live.BROKER_ENV, "redis://localhost:6379")
    assert isinstance(live.heartbeat(RUN), live.Heartbeat)


@pytest.mark.redis
@pytest.mark.skipif(not os.environ.get("SFMKIT_TEST_REDIS"), reason="SFMKIT_TEST_REDIS not set")
def test_a_real_broker_holds_the_alive_key_while_the_run_works():
    run = "test/alive"
    client = redis.Redis.from_url(os.environ["SFMKIT_TEST_REDIS"])
    with live.Heartbeat(client, run, ttl=5):
        assert 0 < client.pttl(live.alive_key(run)) <= 5000
    assert not client.exists(live.alive_key(run))


@pytest.mark.redis
@pytest.mark.skipif(not os.environ.get("SFMKIT_TEST_REDIS"), reason="SFMKIT_TEST_REDIS not set")
def test_a_real_broker_keeps_the_messages_in_order(snapshot):
    run = "test/live"
    publisher = live.RedisPublisher.from_url(os.environ["SFMKIT_TEST_REDIS"], run)
    messages = [live.start_message(run, np.eye(3), ["Img02"]), live.step_message(run, snapshot),
                live.end_message(run, 2, 2)]
    for m in messages:
        publisher.publish(m)
    entries = publisher.client.xrange(live.stream_key(run))
    assert [json.loads(fields[b"data"]) for _, fields in entries] == \
        [json.loads(json.dumps(m)) for m in messages]
    publisher.client.delete(live.stream_key(run))
