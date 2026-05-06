"""Camera sensor abstraction.

Always produces a real ``numpy.ndarray`` BGR frame. Three modes:

* ``synthetic`` (default): renders a procedurally-generated scene with motion,
  people-shaped silhouettes, and scene-specific colour tints. This gives YOLO
  a real image to chew on without requiring a webcam, so the pipeline behaves
  identically on a server, in CI, and on a laptop with a camera.
* ``webcam``: captures from a USB device via ``cv2.VideoCapture`` (set
  ``camera_source`` to an integer index).
* ``rtsp``: capture from an RTSP/HTTP URL.

The frame and a scene descriptor are both attached to the reading; downstream
detectors decide which they need (``MockVisionDetector`` reads the descriptor,
``YoloDetector`` reads the frame).
"""
from __future__ import annotations

import random
from typing import Any

import numpy as np

from app.sensors.base import Sensor, SensorReading

try:  # opencv is in base deps but guard so unit tests don't blow up if missing
    import cv2  # type: ignore[import-untyped]
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]


_SCENES = [
    {"label": "calm_street", "people": (0, 3), "motion": (0.0, 0.2), "weight": 0.55,
     "tint": (35, 35, 50)},
    {"label": "busy_intersection", "people": (8, 25), "motion": (0.2, 0.5), "weight": 0.20,
     "tint": (60, 60, 90)},
    {"label": "loitering", "people": (1, 3), "motion": (0.0, 0.1), "weight": 0.10,
     "tint": (50, 35, 25)},
    {"label": "abandoned_object", "people": (0, 2), "motion": (0.0, 0.05), "weight": 0.05,
     "tint": (60, 30, 80)},
    {"label": "fight", "people": (2, 6), "motion": (0.7, 1.0), "weight": 0.04,
     "tint": (30, 30, 130)},
    {"label": "intrusion", "people": (1, 2), "motion": (0.3, 0.7), "weight": 0.03,
     "tint": (15, 70, 110)},
    {"label": "crowd_anomaly", "people": (20, 60), "motion": (0.5, 0.9), "weight": 0.03,
     "tint": (100, 30, 100)},
]

FRAME_W = 640
FRAME_H = 360


class CameraSensor(Sensor):
    sensor_type = "camera"

    def __init__(self, sensor_id: str, pole_id: str, **kwargs: Any) -> None:
        super().__init__(sensor_id, pole_id, **kwargs)
        self._rng = random.Random(kwargs.get("seed", None))
        self._np_rng = np.random.default_rng(kwargs.get("seed", None))
        self._mode: str = kwargs.get("mode", "synthetic")
        self._source: int | str = kwargs.get("camera_source", 0)
        self._cap = None
        self._t = 0  # frame counter for animation

    def _open_cv_capture(self):
        if cv2 is None or self._cap is not None:
            return self._cap
        cap = cv2.VideoCapture(self._source)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
            self._cap = cap
        return self._cap

    def _pick_scene(self) -> dict[str, Any]:
        weights = [s["weight"] for s in _SCENES]
        return self._rng.choices(_SCENES, weights=weights, k=1)[0]

    def _render_synthetic(self, scene: dict[str, Any], people: int, motion: float) -> np.ndarray:
        """Render a 640×360 BGR frame with people-shaped rectangles + motion noise."""
        frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
        # background tint with mild gradient
        tint = scene["tint"]
        gradient = np.linspace(0.6, 1.0, FRAME_H, dtype=np.float32)[:, None, None]
        frame[:] = (np.array(tint, dtype=np.float32) * gradient).astype(np.uint8)

        if cv2 is not None:
            # ground line
            cv2.line(frame, (0, FRAME_H - 50), (FRAME_W, FRAME_H - 50), (40, 40, 40), 2)
            # motion noise
            if motion > 0:
                noise = self._np_rng.integers(0, int(50 * motion) + 1,
                                              size=(FRAME_H, FRAME_W, 3), dtype=np.int16)
                frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            # draw people rectangles (so YOLO actually picks up "person" class)
            for _ in range(people):
                w = self._rng.randint(35, 60)
                h = self._rng.randint(110, 160)
                x = self._rng.randint(20, FRAME_W - w - 20)
                y = FRAME_H - 50 - h + self._rng.randint(-5, 5)
                colour = (200, 200, 200)
                cv2.rectangle(frame, (x, y), (x + w, y + h), colour, -1)
                # head
                cv2.circle(frame, (x + w // 2, y - 12), 14, colour, -1)
            # scene-specific overlays
            if scene["label"] == "abandoned_object":
                cv2.rectangle(frame, (300, 280), (340, 310), (80, 60, 30), -1)
            if scene["label"] == "fight":
                cv2.line(frame, (250, 260), (340, 220), (30, 30, 200), 4)
            # timestamp / pole watermark
            cv2.putText(frame, f"POLE {self.pole_id}  T={self._t:06d}",
                        (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
        self._t += 1
        return frame

    def _read_frame(self, scene: dict[str, Any], people: int, motion: float) -> np.ndarray:
        if self._mode in {"webcam", "rtsp"} and cv2 is not None:
            cap = self._open_cv_capture()
            if cap is not None and cap.isOpened():
                ok, frame = cap.read()
                if ok and frame is not None:
                    return frame
        return self._render_synthetic(scene, people, motion)

    async def read(self) -> SensorReading:
        scene = self._pick_scene()
        people = self._rng.randint(*scene["people"])
        motion = self._rng.uniform(*scene["motion"])
        frame = self._read_frame(scene, people, motion)
        h, w = frame.shape[:2]
        payload = {
            "scene_label": scene["label"],
            "people_count": people,
            "motion_intensity": round(motion, 3),
            "frame_id": self._t,
            "resolution": f"{w}x{h}",
            "fps": 15,
            "frame": frame,  # numpy ndarray; not serialised over the bus
        }
        return SensorReading(self.sensor_id, self.sensor_type, self.pole_id, payload=payload)

    async def stop(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            finally:
                self._cap = None
