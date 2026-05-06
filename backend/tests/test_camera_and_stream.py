"""Tests for the real CameraSensor + stream processor + MJPEG endpoint."""
from __future__ import annotations

import asyncio

import httpx
import numpy as np
import pytest

from app.ai.audio import AudioPrediction
from app.ai.fusion import FusedThreat
from app.ai.vision import MockVisionDetector, VisionDetection, YoloDetector
from app.db.database import init_db
from app.engine.incident_pipeline import pipeline, seed_default_poles
from app.main import app
from app.sensors.camera import FRAME_H, FRAME_W, CameraSensor
from app.services.stream_processor import StreamProcessor, stream_processor


@pytest.mark.asyncio
async def test_camera_sensor_emits_real_ndarray_frames():
    cam = CameraSensor("test-cam", "POLE-T", seed=1)
    reading = await cam.read()
    frame = reading.payload["frame"]
    # Real BGR frame, correct size and dtype.
    assert isinstance(frame, np.ndarray)
    assert frame.shape == (FRAME_H, FRAME_W, 3)
    assert frame.dtype == np.uint8
    # Reading also keeps the descriptor for the mock detector.
    assert "scene_label" in reading.payload
    assert reading.payload["resolution"] == f"{FRAME_W}x{FRAME_H}"


def test_yolo_coalesce_promotes_overlapping_people_to_violence():
    raw = [
        ("person", 0.9, (100.0, 100.0, 200.0, 300.0)),
        ("person", 0.85, (130.0, 110.0, 230.0, 310.0)),  # heavy overlap
    ]
    out = YoloDetector._coalesce(raw)
    labels = [d.label for d in out]
    assert "violence" in labels


def test_yolo_coalesce_marks_abandoned_object_when_no_one_nearby():
    raw = [("backpack", 0.7, (500.0, 200.0, 560.0, 260.0))]
    out = YoloDetector._coalesce(raw)
    assert any(d.label == "abandoned_object" for d in out)


def test_yolo_coalesce_skips_abandoned_when_person_nearby():
    raw = [
        ("backpack", 0.7, (500.0, 200.0, 560.0, 260.0)),
        ("person", 0.9, (510.0, 195.0, 570.0, 320.0)),
    ]
    out = YoloDetector._coalesce(raw)
    assert not any(d.label == "abandoned_object" for d in out)


@pytest.mark.asyncio
async def test_mock_vision_still_works_on_frame_dict():
    cam = CameraSensor("test-cam-2", "POLE-T", seed=42)
    # Force a "fight" scene by re-seeding deterministically.
    for _ in range(20):
        reading = await cam.read()
        if reading.payload["scene_label"] == "fight":
            break
    det = MockVisionDetector()
    out = det.infer(reading.payload)
    # MockVisionDetector ignores the ndarray and reads scene_label.
    if reading.payload["scene_label"] == "fight":
        assert any(d.label == "violence" for d in out)


@pytest.mark.asyncio
async def test_stream_processor_publishes_jpeg():
    sp = StreamProcessor()
    cam = CameraSensor("c", "POLE-X", seed=7)
    reading = await cam.read()
    sp.annotate_and_publish(
        pole_id="POLE-X",
        frame=reading.payload["frame"],
        vision=[VisionDetection("violence", 0.91, bbox=(100.0, 100.0, 200.0, 300.0))],
        audio=[AudioPrediction("scream", 0.88)],
        threats=[FusedThreat(incident_type="violence", score=0.92, severity="high",
                             sources={"vision": 0.91, "audio": 0.88})],
        scene_label="fight",
    )
    pf = sp.latest("POLE-X")
    assert pf is not None
    # Real JPEG with SOI marker at the start.
    assert pf.jpeg_bytes[:2] == b"\xff\xd8"
    assert pf.threat_score == pytest.approx(0.92)
    assert pf.detections == ["violence 91%"]


@pytest.mark.asyncio
async def test_mjpeg_snapshot_endpoint_returns_jpeg_after_pipeline_tick():
    await init_db()
    await seed_default_poles()
    # Use the real pipeline tick path so we exercise the wiring end-to-end.
    pole = next(iter(pipeline.poles.values()))
    await pipeline._tick_pole(pole)  # type: ignore[attr-defined]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(f"/api/stream/{pole.pole_id}/snapshot")
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "image/jpeg"
        assert r.content[:2] == b"\xff\xd8"

        # missing pole returns 404
        r = await client.get("/api/stream/POLE-DOES-NOT-EXIST/snapshot")
        assert r.status_code == 404


def test_stream_processor_singleton_listed_in_status():
    # singleton is touched by other tests; just confirm shape.
    statuses = stream_processor.all_status()
    assert isinstance(statuses, list)
    if statuses:
        s = statuses[0]
        assert {"pole_id", "updated_at", "threat_score", "detections", "frame_bytes"} <= set(s)


# Quiet "asyncio" import unused for sync tests
_ = asyncio
