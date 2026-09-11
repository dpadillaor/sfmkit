"""The HTTP API, over a store in memory: the API sees the port, not the files."""

from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from contract import STEP_EXAMPLES
from sfmview.adapters.memory_steps import MemoryStepSource
from sfmview.adapters.runs_fs import FsRunStore
from sfmview.api import create_app
from sfmview.domain import Camera, Model, RunId, RunNotFound, RunSummary, Scene
from synthetic import make_run


class MemoryStore:
    """A ``RunStore`` holding one run, for the API alone."""

    def __init__(self, dense: Path | None = None) -> None:
        self.run = RunId("city", "full")
        self.dense = dense

    def runs(self):
        return [RunSummary(self.run, ("colmap", "reconstruct"), "2026-09-10T10:00:00+00:00",
                           {"mean_rotation_error_deg": 0.98}, ("sfmkit", "colmap"),
                           {"match": "cuda", "colmap": "cpu"})]

    def scene(self, run):
        if run != self.run:
            raise RunNotFound(str(run))
        camera = Camera("Img02", np.eye(3), np.zeros(3), np.eye(3), (640, 480))
        points = np.array([[1.0, 2, 3], [np.nan, 0, 0], [4, 5, 6]])
        model = Model("sfmkit", (camera,), points, np.array([[1, 2, 3], [0, 0, 0], [4, 5, 6]],
                                                              dtype=np.uint8))
        return Scene(run, (model,), "Img02", np.eye(4) if self.dense else None)

    def dense_file(self, run):
        if run != self.run or self.dense is None:
            raise RunNotFound(f"{run} has no dense cloud")
        return self.dense


@pytest.fixture
def client():
    return TestClient(create_app(MemoryStore()))


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "live": False}


def test_health_with_live_progress():
    client = TestClient(create_app(MemoryStore(), MemoryStepSource()))
    assert client.get("/api/health").json() == {"status": "ok", "live": True, "broker": "ok"}


def test_runs(client):
    (run,) = client.get("/api/runs").json()
    assert run["id"] == "city/full" and run["project"] == "city" and run["config"] == "full"
    assert run["layers"] == ["sfmkit", "colmap"]
    assert run["metrics"] == {"mean_rotation_error_deg": 0.98}
    assert run["devices"] == {"match": "cuda", "colmap": "cpu"}
    assert run["running"] is None  # no broker to ask


def test_runs_say_which_sfmkit_is_at_work():
    store, steps = MemoryStore(), MemoryStepSource()
    client = TestClient(create_app(store, steps))
    assert client.get("/api/runs").json()[0]["running"] is False
    steps.beat(store.run)
    assert client.get("/api/runs").json()[0]["running"] is True


def test_scene_arrays_go_out_flat_without_nan(client):
    scene = client.get("/api/runs/city/full/scene").json()
    (model,) = scene["models"]
    assert scene["run"] == "city/full" and scene["reference"] == "Img02"
    assert model["points"] == [1, 2, 3, 4, 5, 6]
    assert model["colors"] == [1, 2, 3, 4, 5, 6]
    assert model["to_common"] == np.eye(4).tolist()
    assert model["cameras"][0]["size"] == [640, 480]
    assert scene["dense"] is None


def test_scene_points_to_the_dense_cloud(tmp_path):
    ply = tmp_path / "fused.ply"
    ply.write_bytes(b"ply\n")
    client = TestClient(create_app(MemoryStore(dense=ply)))
    dense = client.get("/api/runs/city/full/scene").json()["dense"]
    assert dense["url"] == "/api/runs/city/full/dense.ply"
    response = client.get(dense["url"])
    assert response.status_code == 200 and response.content == b"ply\n"


@pytest.mark.parametrize("path", [
    "/api/runs/city/nope/scene",
    "/api/runs/city/full/dense.ply",
    "/api/runs/city/..%2F..%2Fetc/scene",
    "/api/runs/.hidden/full/scene",
])
def test_what_is_not_there_is_not_found(client, path):
    assert client.get(path).status_code == 404


def test_the_page_is_served(client):
    page = client.get("/")
    assert page.status_code == 200 and "<canvas" in page.text
    assert client.get("/js/main.js").status_code == 200


def test_the_api_over_real_files(tmp_path):
    make_run(tmp_path, "city", "full", dense=True)
    client = TestClient(create_app(FsRunStore(tmp_path)))
    assert [r["id"] for r in client.get("/api/runs").json()] == ["city/full"]
    scene = client.get("/api/runs/city/full/scene").json()
    assert [m["source"] for m in scene["models"]] == ["sfmkit", "colmap"]
    assert client.get(scene["dense"]["url"]).status_code == 200


def test_live_steps_come_as_history_then_as_they_happen():
    steps = MemoryStepSource()
    run = RunId("city", "full")
    first, second, third = STEP_EXAMPLES[:3]
    steps.publish(run, first)
    steps.publish(run, second)
    client = TestClient(create_app(MemoryStore(), steps))
    with client.websocket_connect("/api/runs/city/full/live") as ws:
        assert isinstance(ws.receive_json()["now"], int)  # the server's clock first
        assert ws.receive_json() == {"id": "1-0", "message": first}
        assert ws.receive_json() == {"id": "2-0", "message": second}
        steps.publish(run, third)
        assert ws.receive_json() == {"id": "3-0", "message": third}


def test_live_steps_resume_after_the_last_seen():
    steps = MemoryStepSource()
    for message in STEP_EXAMPLES[:3]:
        steps.publish(RunId("city", "full"), message)
    client = TestClient(create_app(MemoryStore(), steps))
    with client.websocket_connect("/api/runs/city/full/live?after=2-0") as ws:
        ws.receive_json()
        assert ws.receive_json()["id"] == "3-0"


@pytest.mark.parametrize(("steps", "path", "code"), [
    (None, "/api/runs/city/full/live", 4503),
    (MemoryStepSource(), "/api/runs/.hidden/full/live", 4404),
    (MemoryStepSource(), "/api/runs/city/full/live?after=x", 4404),
])
def test_live_steps_refused(steps, path, code):
    client = TestClient(create_app(MemoryStore(), steps))
    with pytest.raises(WebSocketDisconnect) as closed, client.websocket_connect(path) as ws:
        ws.receive_json()
    assert closed.value.code == code
