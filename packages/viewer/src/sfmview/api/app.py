"""The application, built from whatever implements the ports."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from sfmview.api import live, routes
from sfmview.domain import NotFound
from sfmview.ports import ImageStore, RunStore, StepSource

WEB = Path(__file__).resolve().parent.parent / "web"


def create_app(store: RunStore, steps: StepSource | None = None,
               images: ImageStore | None = None, *, web_dir: Path = WEB) -> FastAPI:
    """The API over ``store``, live progress from ``steps`` and photos from
    ``images`` if given, and the page at ``/``."""
    app = FastAPI(title="sfmview", summary="A web viewer for sfmkit runs.")
    app.state.store = store
    app.state.steps = steps
    app.state.images = images
    app.include_router(routes.router)
    app.include_router(live.router)
    app.add_exception_handler(NotFound, _not_found)
    # Last: the page takes every path the API does not.
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app


async def _not_found(request: Request, exc: NotFound) -> JSONResponse:
    return JSONResponse({"detail": str(exc) or "not found"}, status_code=404)
