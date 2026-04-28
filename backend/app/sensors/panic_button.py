"""Panic button sensor abstraction.

Real hardware would expose a GPIO pin; the simulator allows injecting press
events from API calls or scenario scripts.
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.sensors.base import Sensor, SensorReading


class PanicButtonSensor(Sensor):
    sensor_type = "panic_button"

    def __init__(self, sensor_id: str, pole_id: str, **kwargs: Any) -> None:
        super().__init__(sensor_id, pole_id, **kwargs)
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def trigger(self, latitude: float | None = None, longitude: float | None = None,
                      reporter: str = "anonymous") -> None:
        await self._queue.put({
            "pressed": True,
            "reporter": reporter,
            "latitude": latitude,
            "longitude": longitude,
        })

    async def read(self) -> SensorReading:
        try:
            payload = self._queue.get_nowait()
        except asyncio.QueueEmpty:
            payload = {"pressed": False}
        return SensorReading(self.sensor_id, self.sensor_type, self.pole_id, payload=payload)
