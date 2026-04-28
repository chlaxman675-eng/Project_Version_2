"""Hardware-abstraction base classes for smart-pole sensors.

Concrete drivers can be added later for Raspberry Pi / Jetson by subclassing
``Sensor`` and overriding ``read``. The MVP ships with simulation drivers that
produce realistic synthetic data.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class SensorReading:
    sensor_id: str
    sensor_type: str
    pole_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type,
            "pole_id": self.pole_id,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
        }


class Sensor(abc.ABC):
    """Abstract sensor driver."""

    sensor_type: str = "generic"

    def __init__(self, sensor_id: str, pole_id: str, **kwargs: Any) -> None:
        self.sensor_id = sensor_id
        self.pole_id = pole_id
        self.config = kwargs
        self._healthy = True

    @property
    def healthy(self) -> bool:
        return self._healthy

    @abc.abstractmethod
    async def read(self) -> SensorReading:
        """Produce one reading."""

    async def start(self) -> None:
        """Optional lifecycle hook."""

    async def stop(self) -> None:
        """Optional lifecycle hook."""
