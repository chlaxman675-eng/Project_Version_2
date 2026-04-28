"""Camera sensor abstraction.

The MVP simulator emits scene descriptors (object counts, motion intensity,
synthetic frame metadata). When real hardware is connected, this driver can
be swapped for one that pulls JPEG frames from RTSP/USB and feeds them to
``app.ai.vision``.
"""
from __future__ import annotations

import random
from typing import Any

from app.sensors.base import Sensor, SensorReading

_SCENES = [
    {"label": "calm_street", "people": (0, 3), "motion": (0.0, 0.2), "weight": 0.55},
    {"label": "busy_intersection", "people": (8, 25), "motion": (0.2, 0.5), "weight": 0.20},
    {"label": "loitering", "people": (1, 3), "motion": (0.0, 0.1), "weight": 0.10},
    {"label": "abandoned_object", "people": (0, 2), "motion": (0.0, 0.05), "weight": 0.05},
    {"label": "fight", "people": (2, 6), "motion": (0.7, 1.0), "weight": 0.04},
    {"label": "intrusion", "people": (1, 2), "motion": (0.3, 0.7), "weight": 0.03},
    {"label": "crowd_anomaly", "people": (20, 60), "motion": (0.5, 0.9), "weight": 0.03},
]


class CameraSensor(Sensor):
    sensor_type = "camera"

    def __init__(self, sensor_id: str, pole_id: str, **kwargs: Any) -> None:
        super().__init__(sensor_id, pole_id, **kwargs)
        self._rng = random.Random(kwargs.get("seed", None))

    def _pick_scene(self) -> dict[str, Any]:
        weights = [s["weight"] for s in _SCENES]
        return self._rng.choices(_SCENES, weights=weights, k=1)[0]

    async def read(self) -> SensorReading:
        scene = self._pick_scene()
        people = self._rng.randint(*scene["people"])
        motion = self._rng.uniform(*scene["motion"])
        payload = {
            "scene_label": scene["label"],
            "people_count": people,
            "motion_intensity": round(motion, 3),
            "frame_id": self._rng.randint(1, 1_000_000),
            "resolution": "1280x720",
            "fps": 30,
        }
        return SensorReading(self.sensor_id, self.sensor_type, self.pole_id, payload=payload)
