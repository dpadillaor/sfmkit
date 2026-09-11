"""Every StepSource behaves alike: the one in memory, and Redis when there is one.

Redis is written to as sfmkit writes (JSON in an entry's ``data`` field), so
this is also the viewer's half of the contract with sfmkit's publisher.
"""

import json
import os
import uuid

import anyio
import pytest

from contract import STEP_EXAMPLES, step_errors
from sfmview.adapters.memory_steps import MemoryStepSource
from sfmview.domain import RunId

REDIS = os.environ.get("SFMVIEW_TEST_REDIS")


@pytest.fixture
def anyio_backend():
    return "asyncio"


def memory():
    source = MemoryStepSource(poll=0.01)
    return source, source.publish, lambda: None


def redis_source():
    import redis

    from sfmview.adapters.redis_steps import RedisStepSource, stream_key

    writer = redis.Redis.from_url(REDIS)
    keys = []

    def publish(run, message):
        keys.append(stream_key(run))
        writer.xadd(stream_key(run), {"data": json.dumps(message)})

    source = RedisStepSource.from_url(REDIS, block_ms=100)
    return source, publish, lambda: keys and writer.delete(*keys)


SOURCES = [
    pytest.param(memory, id="memory"),
    pytest.param(redis_source, id="redis", marks=[
        pytest.mark.redis,
        pytest.mark.skipif(not REDIS, reason="SFMVIEW_TEST_REDIS not set")]),
]


@pytest.fixture(params=SOURCES)
def source(request):
    made, publish, cleanup = request.param()
    yield made, publish
    cleanup()


def a_run() -> RunId:
    return RunId("test", uuid.uuid4().hex[:8])  # runs apart from any other test's


async def take(events, n: int) -> list:
    out = []
    with anyio.fail_after(3):
        async for event in events:
            out.append(event)
            if len(out) == n:
                break
    return out


def test_the_examples_keep_to_the_contract():
    assert all(step_errors(m) == [] for m in STEP_EXAMPLES)


@pytest.mark.anyio
async def test_history_first_then_what_comes(source):
    steps, publish = source
    run = a_run()
    first, second, third = STEP_EXAMPLES[:3]
    publish(run, first)
    publish(run, second)
    events = steps.events(run)
    assert [e.message for e in await take(events, 2)] == [first, second]
    publish(run, third)
    assert [e.message for e in await take(events, 1)] == [third]


@pytest.mark.anyio
async def test_reading_resumes_after_an_id(source):
    steps, publish = source
    run = a_run()
    for m in STEP_EXAMPLES[:3]:
        publish(run, m)
    first, *_ = await take(steps.events(run), 1)
    rest = await take(steps.events(run, after=first.id), 2)
    assert [e.message for e in rest] == STEP_EXAMPLES[1:3]


@pytest.mark.anyio
async def test_runs_do_not_mix(source):
    steps, publish = source
    a, b = a_run(), a_run()
    publish(a, STEP_EXAMPLES[0])
    publish(b, STEP_EXAMPLES[2])
    (event,) = await take(steps.events(b), 1)
    assert event.message["kind"] == "end"


@pytest.mark.anyio
async def test_it_can_be_reached(source):
    steps, _ = source
    assert await steps.ping()
