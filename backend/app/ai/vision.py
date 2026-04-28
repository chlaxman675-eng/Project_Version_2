"""Vision detection.

Two interchangeable backends, both implement :class:`VisionDetector`:

* :class:`YoloDetector` — real Ultralytics YOLOv8 inference on a numpy frame.
  Lazy-loads weights on first call so process startup stays fast. Maps COCO
  classes onto SurakshaNet incident labels (e.g. multiple ``person`` boxes
  near each other → ``crowd_anomaly``; ``knife``/``baseball bat`` → ``violence``;
  unattended ``backpack``/``suitcase`` → ``abandoned_object``).
* :class:`MockVisionDetector` — rule-based fallback that reads the synthetic
  scene descriptor; used when YOLO is disabled or when ultralytics fails to
  load (e.g. no network for weights download).

The detector is selected at runtime via ``settings.enable_yolo``.
"""
from __future__ import annotations

import abc
import math
from dataclasses import dataclass
from typing import Any

from loguru import logger

from app.config import get_settings


@dataclass
class VisionDetection:
    label: str  # SurakshaNet canonical label (violence, intrusion, ...)
    confidence: float
    bbox: tuple[float, float, float, float] | None = None  # x1,y1,x2,y2 absolute pixels
    raw_class: str | None = None  # original detector class
    extra: dict[str, Any] | None = None


class VisionDetector(abc.ABC):
    @abc.abstractmethod
    def infer(self, payload: Any) -> list[VisionDetection]:
        ...


# ---------------------------------------------------------------------------
# Mock detector
# ---------------------------------------------------------------------------
class MockVisionDetector(VisionDetector):
    """Maps simulated scene descriptors to detection labels with synthetic bboxes."""

    LABEL_MAP = {
        "fight": "violence",
        "intrusion": "intrusion",
        "abandoned_object": "abandoned_object",
        "crowd_anomaly": "crowd_anomaly",
        "loitering": "loitering",
    }

    def infer(self, payload: Any) -> list[VisionDetection]:
        if not isinstance(payload, dict):
            return []
        scene = payload.get("scene_label", "calm_street")
        motion = float(payload.get("motion_intensity", 0.0))
        people = int(payload.get("people_count", 0))

        out: list[VisionDetection] = []
        if scene in self.LABEL_MAP:
            base = 0.6 + 0.35 * motion
            if scene == "crowd_anomaly":
                base += min(0.2, people / 200)
            out.append(VisionDetection(
                label=self.LABEL_MAP[scene],
                confidence=min(0.99, round(base, 3)),
                # synthetic bbox in centre of frame for visualisation
                bbox=(220.0, 90.0, 420.0, 290.0),
                raw_class=scene,
                extra={"scene": scene, "people_count": people},
            ))
        return out


# ---------------------------------------------------------------------------
# Real YOLO detector
# ---------------------------------------------------------------------------
# COCO classes that map onto our incident schema.
_VIOLENCE_TOOLS = {"knife", "scissors", "baseball bat"}
_ABANDONED_OBJECTS = {"backpack", "suitcase", "handbag", "skateboard", "umbrella"}
_VEHICLE_INTRUSION = {"car", "truck", "motorcycle", "bicycle"}


class YoloDetector(VisionDetector):
    """Real YOLOv8 detector with lazy weight loading."""

    def __init__(self, model_path: str = "yolov8n.pt") -> None:
        self._model_path = model_path
        self._model = None
        self._loaded = False
        self._failed = False

    def _ensure_model(self) -> None:
        if self._loaded or self._failed:
            return
        try:
            from ultralytics import YOLO  # type: ignore[import-not-found]

            self._model = YOLO(self._model_path)
            self._loaded = True
            logger.info("YOLO model loaded: {}", self._model_path)
        except Exception as exc:  # pragma: no cover - environment-specific
            logger.warning("YOLO load failed ({}); falling back to mock for this session", exc)
            self._failed = True

    def _frame(self, payload: Any):
        if hasattr(payload, "shape"):  # already a numpy array
            return payload
        if isinstance(payload, dict) and "frame" in payload and hasattr(payload["frame"], "shape"):
            return payload["frame"]
        return None

    def infer(self, payload: Any) -> list[VisionDetection]:
        frame = self._frame(payload)
        if frame is None:
            return []
        self._ensure_model()
        if not self._loaded or self._model is None:
            return []

        results = self._model.predict(frame, verbose=False, conf=0.25)
        raw: list[tuple[str, float, tuple[float, float, float, float]]] = []
        for r in results:
            names = self._model.names
            for box in r.boxes:
                cls_idx = int(box.cls)
                cls = names[cls_idx]
                conf = float(box.conf)
                xyxy = box.xyxy[0].tolist()
                raw.append((cls, conf, (xyxy[0], xyxy[1], xyxy[2], xyxy[3])))

        return self._coalesce(raw)

    @staticmethod
    def _coalesce(
        raw: list[tuple[str, float, tuple[float, float, float, float]]]
    ) -> list[VisionDetection]:
        """Convert raw COCO detections → SurakshaNet incident-label detections."""
        out: list[VisionDetection] = []
        people = [r for r in raw if r[0] == "person"]
        weapons = [r for r in raw if r[0] in _VIOLENCE_TOOLS]
        bags = [r for r in raw if r[0] in _ABANDONED_OBJECTS]
        vehicles = [r for r in raw if r[0] in _VEHICLE_INTRUSION]

        # violence: weapon visible OR people very close together
        if weapons:
            best = max(weapons, key=lambda r: r[1])
            out.append(VisionDetection(
                label="violence", confidence=min(0.99, 0.7 + best[1] * 0.3),
                bbox=best[2], raw_class=best[0],
                extra={"trigger": "weapon", "people_count": len(people)},
            ))
        elif len(people) >= 2 and YoloDetector._max_overlap(people) > 0.25:
            top = max(people, key=lambda r: r[1])
            out.append(VisionDetection(
                label="violence", confidence=min(0.95, 0.55 + top[1] * 0.4),
                bbox=top[2], raw_class="person×N",
                extra={"trigger": "people_overlap", "people_count": len(people)},
            ))

        # crowd anomaly: many people
        if len(people) >= 5:
            top = max(people, key=lambda r: r[1])
            out.append(VisionDetection(
                label="crowd_anomaly", confidence=min(0.95, 0.5 + len(people) / 30),
                bbox=top[2], raw_class="person×N",
                extra={"people_count": len(people)},
            ))

        # abandoned object: bag + nobody nearby
        for bag in bags:
            if not YoloDetector._has_nearby(bag[2], [p[2] for p in people], radius=120):
                out.append(VisionDetection(
                    label="abandoned_object", confidence=min(0.9, 0.5 + bag[1] * 0.4),
                    bbox=bag[2], raw_class=bag[0],
                    extra={"object": bag[0]},
                ))

        # intrusion: vehicle in frame (proxy)
        if vehicles:
            best = max(vehicles, key=lambda r: r[1])
            out.append(VisionDetection(
                label="intrusion", confidence=min(0.85, 0.45 + best[1] * 0.4),
                bbox=best[2], raw_class=best[0],
                extra={"vehicle": best[0]},
            ))

        # loitering: 1-2 people, low movement (movement signal not available here -
        # caller can post-filter using motion sensor; we emit low-conf hint).
        if 1 <= len(people) <= 2 and not out:
            top = max(people, key=lambda r: r[1])
            out.append(VisionDetection(
                label="loitering", confidence=min(0.7, 0.4 + top[1] * 0.3),
                bbox=top[2], raw_class=top[0],
                extra={"people_count": len(people)},
            ))

        return out

    @staticmethod
    def _box_area(b: tuple[float, float, float, float]) -> float:
        return max(0.0, (b[2] - b[0])) * max(0.0, (b[3] - b[1]))

    @staticmethod
    def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
        x1, y1 = max(a[0], b[0]), max(a[1], b[1])
        x2, y2 = min(a[2], b[2]), min(a[3], b[3])
        inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        union = YoloDetector._box_area(a) + YoloDetector._box_area(b) - inter
        return inter / union if union > 0 else 0.0

    @staticmethod
    def _max_overlap(people: list[tuple[str, float, tuple[float, float, float, float]]]) -> float:
        best = 0.0
        for i in range(len(people)):
            for j in range(i + 1, len(people)):
                best = max(best, YoloDetector._iou(people[i][2], people[j][2]))
        return best

    @staticmethod
    def _has_nearby(
        target: tuple[float, float, float, float],
        others: list[tuple[float, float, float, float]],
        radius: float,
    ) -> bool:
        cx, cy = (target[0] + target[2]) / 2, (target[1] + target[3]) / 2
        for o in others:
            ox, oy = (o[0] + o[2]) / 2, (o[1] + o[3]) / 2
            if math.hypot(cx - ox, cy - oy) < radius:
                return True
        return False


class HybridDetector(VisionDetector):
    """Runs YOLO on the ndarray and the mock on the scene descriptor, then merges.

    On a real RTSP/webcam stream YOLO carries the load; on synthetic frames the
    mock fills in (synthetic shapes don't fire YOLO's COCO classes). De-dupes
    by label, keeping the higher-confidence detection per label.
    """

    def __init__(self, yolo: YoloDetector, mock: MockVisionDetector) -> None:
        self._yolo = yolo
        self._mock = mock

    def infer(self, payload: Any) -> list[VisionDetection]:
        merged: dict[str, VisionDetection] = {}
        for det in self._yolo.infer(payload) + self._mock.infer(payload):
            existing = merged.get(det.label)
            if existing is None or det.confidence > existing.confidence:
                merged[det.label] = det
        return list(merged.values())


def build_default_detector() -> VisionDetector:
    settings = get_settings()
    mock = MockVisionDetector()
    if settings.enable_yolo:
        try:
            return HybridDetector(YoloDetector(settings.yolo_model), mock)
        except Exception as exc:  # pragma: no cover
            logger.warning("YoloDetector init failed ({}); using mock", exc)
    return mock
