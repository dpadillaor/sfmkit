"""The JSON API, under ``/api``."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from sfmview.api.schemas import RunOut, SceneOut
from sfmview.domain import RunId
from sfmview.ports import RunStore

router = APIRouter(prefix="/api")


def get_store(request: Request) -> RunStore:
    return request.app.state.store


Store = Annotated[RunStore, Depends(get_store)]


def get_run(project: str, config: str) -> RunId:
    try:
        return RunId(project, config)
    except ValueError:
        # Not a name a run can have: as unknown as any other missing run.
        raise HTTPException(status_code=404, detail="no such run") from None


Run = Annotated[RunId, Depends(get_run)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/runs")
def runs(store: Store) -> list[RunOut]:
    return [RunOut.of(r) for r in store.runs()]


@router.get("/runs/{project}/{config}/scene")
def scene(run: Run, store: Store) -> SceneOut:
    return SceneOut.of(store.scene(run))


@router.get("/runs/{project}/{config}/dense.ply")
def dense(run: Run, store: Store) -> FileResponse:
    return FileResponse(store.dense_file(run), media_type="application/octet-stream",
                        filename=f"{run.project}_{run.config}_fused.ply")
