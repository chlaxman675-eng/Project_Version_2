"""Pole telemetry: power, battery, network, env."""
from __future__ import annotations

import random
from typing import Any

from app.sensors.base import Sensor, SensorReading


class TelemetrySensor(Sensor):
    sensor_type = "telemetry"

    def __init__(self, sensor_id: str, pole_id: str, **kwargs: Any) -> None:
        super().__init__(sensor_id, pole_id, **kwargs)
        self._rng = random.Random(kwargs.get("seed"))
        self._battery = self._rng.uniform(70, 100)

    async def read(self) -> SensorReading:
        # gentle drift
        self._battery = max(10.0, self._battery - self._rng.uniform(0.0, 0.05))
        if self._rng.random() < 0.03:
            self._battery = min(100.0, self._battery + self._rng.uniform(2, 5))  # solar charge
        payload = {
            "battery_pct": round(self._battery, 2),
            "solar_input_w": round(self._rng.uniform(0, 35), 2),
            "cpu_temp_c": round(self._rng.uniform(35, 78), 1),
            "network_latency_ms": round(self._rng.uniform(8, 90), 1),
            "uptime_s": self._rng.randint(1000, 1_000_000),
        }
        return SensorReading(self.sensor_id, self.sensor_type, self.pole_id, payload=payload)
