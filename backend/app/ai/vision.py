"""Vision detection.

Architecture is upgradeable: when ``settings.enable_yolo`` is True and
``ultralytics`` is installed, ``YoloDetector`` runs YOLOv8 on real frames.
Otherwise the lightweight ``MockVisionDetector`` interprets simulated camera
scene descriptors and outputs class confidences. Both implement the same
``VisionDetector`` interface so callers don't change.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any

from app.config import get_settings


@dataclass
class VisionDetection:
    label: str
    confidence: float
    bbox: tuple[float, float, float, float] | None = None  # x,y,w,h normalised
    extra: dict[str, Any] | None = None


class VisionDetector(abc.ABC):
    @abc.abstractmethod
    def infer(self, frame: Any) -> list[VisionDetection]:
        ...


class MockVisionDetector(VisionDetector):
    """Maps simulated scene descriptors to detection labels.

    ``frame`` here is a dict from :class:`app.sensors.camera.CameraSensor`.
    """

    LABEL_MAP = {
        "fight": "violence",
        "intrusion": "intrusion",
        "abandoned_object": "abandoned_object",
        "crowd_anomaly": "crowd_anomaly",
        "loitering": "loitering",
    }

    def infer(self, frame: Any) -> list[VisionDetection]:
        if not isinstance(frame, dict):
            return []
        scene = frame.get("scene_label", "calm_street")
        motion = float(frame.get("motion_intensity", 0.0))
        people = int(frame.get("people_count", 0))

        out: list[VisionDetection] = []
        if scene in self.LABEL_MAP:
            base = 0.6 + 0.35 * motion
            if scene == "crowd_anomaly":
                base += min(0.2, people / 200)
            out.append(VisionDetection(
                label=self.LABEL_MAP[scene],
                confidence=min(0.99, round(base, 3)),
                extra={"scene": scene, "people_count": people},
            ))
        return out


class YoloDetector(VisionDetector):  # pragma: no cover - exercised only when YOLO is installed
    """Real YOLOv8 detector. Lazy import so the MVP runs without torch/ultralytics."""

    HARMFUL_CLASSES = {"person", "knife", "scissors", "baseball bat", "backpack", "suitcase"}

    def __init__(self, model_path: str) -> None:
        from ultralytics import YOLO  # type: ignore[import-not-found]
        self._model = YOLO(model_path)

    def infer(self, frame: Any) -> list[VisionDetection]:
        results = self._model.predict(frame, verbose=False)
        out: list[VisionDetection] = []
        for r in results:
            for box in r.boxes:
                cls = self._model.names[int(box.cls)]
                conf = float(box.conf)
                xywhn = box.xywhn[0].tolist()
                out.append(VisionDetection(label=cls, confidence=conf, bbox=tuple(xywhn)))
        return out


def build_default_detector() -> VisionDetector:
    settings = get_settings()
    if settings.enable_yolo:
        try:
            return YoloDetector(settings.yolo_model)
        except Exception:
            return MockVisionDetector()
    return MockVisionDetector()
