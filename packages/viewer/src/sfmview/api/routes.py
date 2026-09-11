"""The JSON API, under ``/api``."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from sfmview.api.schemas import RunOut, SceneOut
from sfmview.domain import ImageNotFound, RunId
from sfmview.ports import ImageStore, RunStore

router = APIRouter(prefix="/api")


def get_store(request: Request) -> RunStore:
    return request.app.state.store


Store = Annotated[RunStore, Depends(get_store)]


def get_images(request: Request) -> ImageStore:
    images = request.app.state.images
    if images is None:
        raise ImageNotFound("this server has no photos")
    return images


Images = Annotated[ImageStore, Depends(get_images)]


def get_run(project: str, config: str) -> RunId:
    try:
        return RunId(project, config)
    except ValueError:
        # Not a name a run can have: as unknown as any other missing run.
        raise HTTPException(status_code=404, detail="no such run") from None


Run = Annotated[RunId, Depends(get_run)]


@router.get("/health")
async def health(request: Request) -> dict[str, str | bool]:
    """Up, and whether live progress is on and its broker reachable."""
    steps = request.app.state.steps
    if steps is None:
        return {"status": "ok", "live": False}
    return {"status": "ok", "live": True, "broker": "ok" if await steps.ping() else "unreachable"}


@router.get("/runs")
async def runs(request: Request, store: Store) -> list[RunOut]:
    """Every run, and whether sfmkit is at work on it, if there is a broker to ask."""
    summaries = await run_in_threadpool(store.runs)
    steps = request.app.state.steps
    alive = None if steps is None else await steps.running([r.run for r in summaries])
    return [RunOut.of(r, None if alive is None else r.run in alive) for r in summaries]


@router.get("/runs/{project}/{config}/scene")
def scene(run: Run, store: Store) -> SceneOut:
    return SceneOut.of(store.scene(run))


@router.get("/runs/{project}/{config}/dense.ply")
def dense(run: Run, store: Store) -> FileResponse:
    return FileResponse(store.dense_file(run), media_type="application/octet-stream",
                        filename=f"{run.project}_{run.config}_fused.ply")


@router.get("/datasets/{dataset}/images/{name}")
def image(dataset: str, name: str, images: Images) -> FileResponse:
    """A photo, as it is; the browser caches it for an hour."""
    return FileResponse(images.image_file(dataset, name),
                        headers={"Cache-Control": "private, max-age=3600"})
