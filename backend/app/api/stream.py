"""HTTP MJPEG endpoint for the per-pole annotated camera stream.

The pipeline runs YOLO on every camera frame and stores the annotated JPEG via
``app.services.stream_processor``. This router exposes that buffer as a
``multipart/x-mixed-replace`` MJPEG stream that any ``<img>`` tag can render.

Auth deliberately omitted on this route so the operator dashboard can render
``<img src="/api/stream/POLE-001/mjpeg">`` directly. Add a token check before
shipping to production.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.services.stream_processor import stream_processor

router = APIRouter()


@router.get("/stream/poles", tags=["stream"])
async def list_streams() -> dict:
    return {"streams": stream_processor.all_status()}


@router.get("/stream/{pole_id}/snapshot", tags=["stream"])
async def snapshot(pole_id: str) -> Response:
    pf = stream_processor.latest(pole_id)
    if pf is None:
        raise HTTPException(status_code=404, detail="no frame yet for pole")
    return Response(content=pf.jpeg_bytes, media_type="image/jpeg")


@router.get("/stream/{pole_id}/mjpeg", tags=["stream"])
async def mjpeg_stream(pole_id: str) -> StreamingResponse:
    if stream_processor.latest(pole_id) is None:
        raise HTTPException(status_code=404, detail="no frame yet for pole")

    async def gen():
        async for chunk in stream_processor.stream(pole_id):
            yield chunk

    return StreamingResponse(
        gen(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"},
    )
