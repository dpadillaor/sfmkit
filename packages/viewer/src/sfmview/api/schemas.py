"""The API's JSON, and how domain values become it.

Arrays go out flat (``[x0, y0, z0, x1, ...]``), as the browser's buffers want
them, and matrices row-major. Coordinates keep OpenCV's axes; the page turns
them into three.js's.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel

from sfmview.domain import Camera, Model, RunSummary, Scene


class CameraOut(BaseModel):
    name: str
    R: list[list[float]]  # world to camera
    t: list[float]
    K: list[list[float]] | None
    size: tuple[int, int] | None  # width, height
    query: bool

    @classmethod
    def of(cls, c: Camera) -> CameraOut:
        return cls(name=c.name, R=c.R.tolist(), t=c.t.tolist(),
                   K=None if c.K is None else c.K.tolist(), size=c.size, query=c.query)


class ModelOut(BaseModel):
    source: str
    cameras: list[CameraOut]
    points: list[float]  # flat xyz
    colors: list[int] | None  # flat rgb, 0-255
    to_common: list[list[float]]  # 4x4, into the scene's shared frame

    @classmethod
    def of(cls, m: Model) -> ModelOut:
        finite = np.isfinite(m.points).all(axis=1)  # JSON has no NaN
        colors = None if m.colors is None else m.colors[finite].ravel().tolist()
        return cls(source=m.source, cameras=[CameraOut.of(c) for c in m.cameras],
                   points=np.round(m.points[finite], 5).ravel().tolist(), colors=colors,
                   to_common=m.to_common.tolist())


class DenseOut(BaseModel):
    url: str  # a binary PLY
    to_common: list[list[float]]


class SceneOut(BaseModel):
    run: str
    reference: str | None
    models: list[ModelOut]
    dense: DenseOut | None
    images: str | None  # where the photos are: <images>/<name>

    @classmethod
    def of(cls, s: Scene) -> SceneOut:
        dense = None
        if s.dense_to_common is not None:
            url = f"/api/runs/{s.run.project}/{s.run.config}/dense.ply"
            dense = DenseOut(url=url, to_common=s.dense_to_common.tolist())
        images = None if s.dataset is None else f"/api/datasets/{s.dataset}/images"
        return cls(run=str(s.run), reference=s.reference,
                   models=[ModelOut.of(m) for m in s.models], dense=dense, images=images)


class RunOut(BaseModel):
    id: str  # "<project>/<config>"
    project: str
    config: str
    stages: list[str]
    updated: str | None
    metrics: dict[str, float | None]
    layers: list[str]
    running: bool | None  # sfmkit at work on it now; None, no broker to ask

    @classmethod
    def of(cls, r: RunSummary, running: bool | None = None) -> RunOut:
        return cls(id=str(r.run), project=r.run.project, config=r.run.config,
                   stages=list(r.stages), updated=r.updated, metrics=dict(r.metrics),
                   layers=list(r.layers), running=running)
