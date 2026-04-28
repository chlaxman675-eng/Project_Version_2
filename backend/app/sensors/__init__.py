"""Sensor abstractions for the smart pole."""
from app.sensors.audio import AudioSensor
from app.sensors.base import Sensor, SensorReading
from app.sensors.camera import CameraSensor
from app.sensors.motion import MotionSensor
from app.sensors.panic_button import PanicButtonSensor
from app.sensors.telemetry import TelemetrySensor

__all__ = [
    "Sensor",
    "SensorReading",
    "CameraSensor",
    "AudioSensor",
    "MotionSensor",
    "PanicButtonSensor",
    "TelemetrySensor",
]
