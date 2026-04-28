"""Audio (microphone) sensor abstraction."""
from __future__ import annotations

import random
from typing import Any

from app.sensors.base import Sensor, SensorReading

_AUDIO_EVENTS = [
    {"label": "ambient", "db": (35, 55), "weight": 0.78},
    {"label": "traffic", "db": (55, 75), "weight": 0.10},
    {"label": "shouting", "db": (75, 92), "weight": 0.05},
    {"label": "scream", "db": (85, 100), "weight": 0.03},
    {"label": "gunshot", "db": (110, 140), "weight": 0.02},
    {"label": "glass_break", "db": (80, 100), "weight": 0.02},
]


class AudioSensor(Sensor):
    sensor_type = "audio"

    def __init__(self, sensor_id: str, pole_id: str, **kwargs: Any) -> None:
        super().__init__(sensor_id, pole_id, **kwargs)
        self._rng = random.Random(kwargs.get("seed"))

    async def read(self) -> SensorReading:
        weights = [e["weight"] for e in _AUDIO_EVENTS]
        event = self._rng.choices(_AUDIO_EVENTS, weights=weights, k=1)[0]
        db = self._rng.uniform(*event["db"])
        payload = {
            "event_label": event["label"],
            "db_level": round(db, 1),
            "duration_ms": self._rng.randint(120, 1500),
            "spectral_centroid": self._rng.uniform(500, 4500),
        }
        return SensorReading(self.sensor_id, self.sensor_type, self.pole_id, payload=payload)
