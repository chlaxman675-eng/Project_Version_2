"""WebSocket hub for live dashboard updates."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.engine.event_bus import bus

router = APIRouter()


@router.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    async with bus.subscribe("*") as q:
        try:
            await websocket.send_text(json.dumps({"topic": "hello", "msg": "connected"}))
            while True:
                # Race websocket recv (for ping/keepalive) with bus messages.
                recv_task = asyncio.create_task(websocket.receive_text())
                bus_task = asyncio.create_task(q.get())
                done, pending = await asyncio.wait(
                    [recv_task, bus_task], return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()
                if recv_task in done:
                    try:
                        recv_task.result()
                    except WebSocketDisconnect:
                        return
                    except Exception:
                        return
                if bus_task in done:
                    msg = bus_task.result()
                    await websocket.send_text(json.dumps(msg, default=str))
        except WebSocketDisconnect:
            return
