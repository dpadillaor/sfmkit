"""A run's live progress, over a WebSocket.

The server first sends ``{"now": <milliseconds>}``, its clock, then
``{"id": ..., "message": {...}}``, one per message of the run's stream: the
history first, then each new one. An id starts with the milliseconds it was
written at, so a client can tell what happened after it connected, on one
clock. A client that reconnects passes the last id it saw as ``?after=`` and
misses nothing.
"""

from __future__ import annotations

import re
import time

import anyio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from sfmview.domain import RunId

router = APIRouter(prefix="/api")

_ID = re.compile(r"0|\d+-\d+")

# Close codes, in the range left to applications.
NOT_A_RUN = 4404
LIVE_OFF = 4503


@router.websocket("/runs/{project}/{config}/live")
async def live(websocket: WebSocket, project: str, config: str, after: str = "0") -> None:
    source = websocket.app.state.steps
    try:
        run = RunId(project, config)
    except ValueError:
        run = None
    # Accepted before any refusal: a close before the handshake reaches a
    # browser as a bare HTTP 403, without the code saying why.
    await websocket.accept()
    if run is None or not _ID.fullmatch(after):
        await websocket.close(code=NOT_A_RUN)
        return
    if source is None:
        await websocket.close(code=LIVE_OFF)
        return

    await websocket.send_json({"now": round(time.time() * 1000)})
    async with anyio.create_task_group() as tasks:

        async def forward() -> None:
            try:
                async for event in source.events(run, after):
                    await websocket.send_json({"id": event.id, "message": event.message})
            except (WebSocketDisconnect, RuntimeError):
                pass  # the client left while a message was on its way
            tasks.cancel_scope.cancel()

        async def until_closed() -> None:
            # The client sends nothing; this only notices when it leaves, which
            # a sender blocked waiting for new messages would not.
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                pass
            tasks.cancel_scope.cancel()

        tasks.start_soon(forward)
        tasks.start_soon(until_closed)
