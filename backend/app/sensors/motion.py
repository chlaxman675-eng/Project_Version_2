"""PIR / radar motion sensor abstraction."""
from __future__ import annotations

import random
from typing import Any

from app.sensors.base import Sensor, SensorReading


class MotionSensor(Sensor):
    sensor_type = "motion"

    def __init__(self, sensor_id: str, pole_id: str, **kwargs: Any) -> None:
        super().__init__(sensor_id, pole_id, **kwargs)
        self._rng = random.Random(kwargs.get("seed"))

    async def read(self) -> SensorReading:
        triggered = self._rng.random() < 0.18
        velocity = self._rng.uniform(0.0, 1.5) if triggered else 0.0
        return SensorReading(
            self.sensor_id,
            self.sensor_type,
            self.pole_id,
            payload={"triggered": triggered, "velocity_mps": round(velocity, 2)},
        )
