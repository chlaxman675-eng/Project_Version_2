"""Annotated MJPEG stream buffer.

The incident pipeline already runs YOLO on every camera frame. This service
sits next to the pipeline and keeps the most recent annotated JPEG per pole so
the dashboard can fetch a continuous MJPEG stream at ``/api/stream/{pole}/mjpeg``.

It is *not* a separate inference loop — that would double-run the model. It is
a thin overlay layer fed by ``IncidentPipeline._tick_pole``.
"""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
from loguru import logger

from app.ai.audio import AudioPrediction
from app.ai.fusion import FusedThreat
from app.ai.vision import VisionDetection

try:
    import cv2  # type: ignore[import-untyped]
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]


# Severity → BGR colour for bbox/banner overlays.
_SEVERITY_COLOURS = {
    "low": (60, 200, 255),      # amber
    "medium": (0, 165, 255),    # orange
    "high": (40, 60, 230),      # red
    "critical": (40, 30, 200),  # deeper red
}
_DEFAULT_COLOUR = (220, 220, 220)


@dataclass
class PoleFrame:
    pole_id: str
    jpeg_bytes: bytes
    updated_at: datetime
    threat_score: float = 0.0
    detections: list[str] = field(default_factory=list)


class StreamProcessor:
    """Per-pole rolling annotated-frame buffer with async fan-out."""

    def __init__(self, jpeg_quality: int = 70) -> None:
        self._frames: dict[str, PoleFrame] = {}
        self._waiters: dict[str, list[asyncio.Event]] = {}
        self._lock = asyncio.Lock()
        self._jpeg_quality = jpeg_quality

    # ------------------------------------------------------------------ ingest
    def annotate_and_publish(
        self,
        *,
        pole_id: str,
        frame: np.ndarray | None,
        vision: list[VisionDetection],
        audio: list[AudioPrediction],
        threats: list[FusedThreat],
        scene_label: str,
    ) -> None:
        """Draw bboxes + labels + banner onto the frame and store the JPEG."""
        if frame is None or cv2 is None:
            return
        annotated = self._draw_overlay(frame.copy(), vision, audio, threats, scene_label, pole_id)
        ok, buf = cv2.imencode(
            ".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), self._jpeg_quality]
        )
        if not ok:
            return
        score = max((t.score for t in threats), default=0.0)
        labels = [f"{d.label} {int(d.confidence * 100)}%" for d in vision]
        self._frames[pole_id] = PoleFrame(
            pole_id=pole_id,
            jpeg_bytes=buf.tobytes(),
            updated_at=datetime.now(timezone.utc),
            threat_score=score,
            detections=labels,
        )
        for ev in self._waiters.get(pole_id, []):
            ev.set()

    @staticmethod
    def _draw_overlay(
        frame: np.ndarray,
        vision: list[VisionDetection],
        audio: list[AudioPrediction],
        threats: list[FusedThreat],
        scene_label: str,
        pole_id: str,
    ) -> np.ndarray:
        if cv2 is None:
            return frame
        h, w = frame.shape[:2]
        # Highest-severity threat drives banner colour
        top_threat = max(threats, key=lambda t: t.score, default=None)
        banner_colour = _SEVERITY_COLOURS.get(top_threat.severity, _DEFAULT_COLOUR) \
            if top_threat else (60, 90, 60)

        # Top status banner
        cv2.rectangle(frame, (0, 0), (w, 26), banner_colour, -1)
        status = (f"THREAT {top_threat.incident_type.upper()} {top_threat.score:.2f}"
                  if top_threat else f"SCENE {scene_label}")
        cv2.putText(frame, f"{pole_id}  {status}", (8, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

        # Bounding boxes
        for d in vision:
            if not d.bbox:
                continue
            x1, y1, x2, y2 = (int(v) for v in d.bbox)
            x1, y1 = max(0, x1), max(28, y1)
            x2, y2 = min(w - 1, x2), min(h - 1, y2)
            severity = _severity_for_label(d.label, threats)
            colour = _SEVERITY_COLOURS.get(severity, _DEFAULT_COLOUR)
            cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 2)
            text = f"{d.label} {int(d.confidence * 100)}%"
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, max(28, y1 - th - 6)),
                          (x1 + tw + 6, y1), colour, -1)
            cv2.putText(frame, text, (x1 + 3, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        # Audio chip
        if audio:
            chip = "AUDIO " + ", ".join(f"{a.label} {int(a.confidence * 100)}%" for a in audio)
            cv2.rectangle(frame, (0, h - 22), (min(w, 12 + 7 * len(chip)), h), (30, 30, 30), -1)
            cv2.putText(frame, chip, (6, h - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 220, 60), 1)

        return frame

    # --------------------------------------------------------------- fan-out
    async def stream(self, pole_id: str, fps_cap: float = 8.0) -> Iterable[bytes]:
        """Async generator yielding multipart MJPEG chunks for one pole."""
        boundary = b"--frame"
        min_interval = 1.0 / max(0.5, fps_cap)
        last_id: int | None = None
        while True:
            event = asyncio.Event()
            self._waiters.setdefault(pole_id, []).append(event)
            try:
                pf = self._frames.get(pole_id)
                if pf is not None and id(pf) != last_id:
                    last_id = id(pf)
                    yield (
                        boundary
                        + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                        + str(len(pf.jpeg_bytes)).encode()
                        + b"\r\n\r\n"
                        + pf.jpeg_bytes
                        + b"\r\n"
                    )
                    await asyncio.sleep(min_interval)
                else:
                    try:
                        await asyncio.wait_for(event.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        # heartbeat keeps the connection alive
                        if pf is not None:
                            yield (
                                boundary
                                + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                + str(len(pf.jpeg_bytes)).encode()
                                + b"\r\n\r\n"
                                + pf.jpeg_bytes
                                + b"\r\n"
                            )
            finally:
                waiters = self._waiters.get(pole_id, [])
                if event in waiters:
                    waiters.remove(event)

    def latest(self, pole_id: str) -> PoleFrame | None:
        return self._frames.get(pole_id)

    def all_status(self) -> list[dict]:
        return [
            {
                "pole_id": pf.pole_id,
                "updated_at": pf.updated_at.isoformat(),
                "threat_score": pf.threat_score,
                "detections": pf.detections,
                "frame_bytes": len(pf.jpeg_bytes),
            }
            for pf in self._frames.values()
        ]


def _severity_for_label(label: str, threats: list[FusedThreat]) -> str:
    for t in threats:
        if t.incident_type == label:
            return t.severity
    return "low"


# Singleton shared by the pipeline + the MJPEG endpoint.
stream_processor = StreamProcessor()


__all__ = ["StreamProcessor", "stream_processor", "PoleFrame"]


# Quiet "logger imported but unused" linters in case overlay branch is skipped.
_ = logger
