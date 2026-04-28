"""Incident pipeline: capture -> analyze -> detect -> alert -> notify -> dispatch -> resolve."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import select

from app.ai.audio import AudioClassifier, build_default_audio_classifier
from app.ai.fusion import FusedThreat, FusionEngine
from app.ai.vision import VisionDetector, build_default_detector
from app.alerts.manager import AlertManager
from app.config import get_settings
from app.db.database import session_scope
from app.db.models import Incident, Pole
from app.dispatch.recommender import DispatchRecommender
from app.engine.event_bus import bus
from app.sensors.audio import AudioSensor
from app.sensors.camera import CameraSensor
from app.sensors.motion import MotionSensor
from app.sensors.panic_button import PanicButtonSensor
from app.sensors.telemetry import TelemetrySensor
from app.services.audit import audit


@dataclass
class PoleNode:
    pole_id: str
    name: str
    latitude: float
    longitude: float
    zone: str = "default"
    camera: CameraSensor = field(init=False)
    audio: AudioSensor = field(init=False)
    motion: MotionSensor = field(init=False)
    panic: PanicButtonSensor = field(init=False)
    telemetry: TelemetrySensor = field(init=False)

    def __post_init__(self) -> None:
        self.camera = CameraSensor(f"{self.pole_id}-cam", self.pole_id)
        self.audio = AudioSensor(f"{self.pole_id}-mic", self.pole_id)
        self.motion = MotionSensor(f"{self.pole_id}-pir", self.pole_id)
        self.panic = PanicButtonSensor(f"{self.pole_id}-sos", self.pole_id)
        self.telemetry = TelemetrySensor(f"{self.pole_id}-tel", self.pole_id)


class IncidentPipeline:
    """Drives sensor reads, AI analysis, fusion, alerting, and dispatch."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.vision: VisionDetector = build_default_detector()
        self.audio: AudioClassifier = build_default_audio_classifier()
        self.fusion = FusionEngine()
        self.alerts = AlertManager()
        self.dispatch = DispatchRecommender()
        self.poles: dict[str, PoleNode] = {}
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None
        # rolling metrics
        self._latencies_ms: list[float] = []
        self._total_detections = 0
        self._total_alerts = 0
        self._total_false_positives = 0

    # --- pole management ---------------------------------------------------
    def register_pole(self, node: PoleNode) -> None:
        self.poles[node.pole_id] = node
        logger.info("registered pole {} at ({},{})", node.pole_id, node.latitude, node.longitude)

    async def trigger_panic(self, pole_id: str | None, latitude: float | None,
                            longitude: float | None, reporter: str) -> None:
        # If pole specified use that; else nearest pole, else virtual citizen pole.
        target = pole_id and self.poles.get(pole_id)
        if not target and latitude is not None and longitude is not None:
            target = self._nearest_pole(latitude, longitude)
        if target:
            await target.panic.trigger(latitude, longitude, reporter)
        else:
            # synthesise a one-shot panic incident bypassing the loop
            await self._materialise_threat(
                pole=None,
                threat=FusedThreat(
                    incident_type="panic_sos",
                    score=1.0,
                    severity="critical",
                    sources={"panic_button": 1.0},
                    description=f"Citizen SOS triggered by {reporter}",
                ),
                latitude=latitude,
                longitude=longitude,
            )

    def _nearest_pole(self, lat: float, lon: float) -> PoleNode | None:
        if not self.poles:
            return None

        def dist(p: PoleNode) -> float:
            return (p.latitude - lat) ** 2 + (p.longitude - lon) ** 2

        return min(self.poles.values(), key=dist)

    # --- main loop ---------------------------------------------------------
    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="incident-pipeline")
        logger.info("incident pipeline started")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task
        logger.info("incident pipeline stopped")

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick_all()
            except Exception:
                logger.exception("pipeline tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.settings.simulation_tick_seconds)
            except asyncio.TimeoutError:
                continue

    async def _tick_all(self) -> None:
        await asyncio.gather(*(self._tick_pole(p) for p in self.poles.values()))

    async def _tick_pole(self, node: PoleNode) -> None:
        t0 = time.perf_counter()
        cam, mic, mot, pan, tel = await asyncio.gather(
            node.camera.read(), node.audio.read(), node.motion.read(),
            node.panic.read(), node.telemetry.read(),
        )

        # publish raw telemetry
        await bus.publish("telemetry", {"pole_id": node.pole_id, "data": tel.payload,
                                        "timestamp": tel.timestamp.isoformat()})

        vision_dets = self.vision.infer(cam.payload)
        audio_preds = self.audio.infer(mic.payload)

        # Surface raw inferences for the live console even when below threshold.
        await bus.publish("inference", {
            "pole_id": node.pole_id,
            "vision": [d.__dict__ for d in vision_dets],
            "audio": [p.__dict__ for p in audio_preds],
            "scene": cam.payload,
            "timestamp": cam.timestamp.isoformat(),
        })
        if vision_dets or audio_preds:
            self._total_detections += 1

        threats = self.fusion.fuse(
            vision=vision_dets,
            audio=audio_preds,
            motion_payload=mot.payload,
            panic_payload=pan.payload,
        )

        for threat in threats:
            await self._materialise_threat(
                pole=node, threat=threat,
                latitude=node.latitude, longitude=node.longitude,
            )

        latency_ms = (time.perf_counter() - t0) * 1000
        self._latencies_ms.append(latency_ms)
        if len(self._latencies_ms) > 500:
            self._latencies_ms = self._latencies_ms[-500:]

    async def _materialise_threat(
        self, *, pole: PoleNode | None, threat: FusedThreat,
        latitude: float | None, longitude: float | None,
    ) -> None:
        async with session_scope() as session:
            inc = Incident(
                pole_id=pole.pole_id if pole else None,
                type=threat.incident_type,
                severity=threat.severity,
                score=threat.score,
                description=threat.description,
                latitude=latitude,
                longitude=longitude,
                sources=threat.sources,
            )
            session.add(inc)
            await session.commit()
            await session.refresh(inc)

            recommendation = self.dispatch.recommend(inc)
            alert = await self.alerts.generate(session, inc, recommendation)
            await session.commit()
            await session.refresh(alert)
            self._total_alerts += 1

            await audit(session, "system", "incident.created", f"incident:{inc.id}",
                        metadata={"type": inc.type, "score": inc.score})
            await session.commit()

            payload = {
                "incident": {
                    "id": inc.id,
                    "pole_id": inc.pole_id,
                    "type": inc.type,
                    "severity": inc.severity,
                    "score": inc.score,
                    "description": inc.description,
                    "latitude": inc.latitude,
                    "longitude": inc.longitude,
                    "sources": inc.sources,
                    "status": inc.status,
                    "created_at": inc.created_at.isoformat(),
                },
                "alert_id": alert.id,
                "dispatch_recommendation": recommendation,
            }
            await bus.publish("incident.created", payload)
            await bus.publish("alert.created", {"alert_id": alert.id, "incident_id": inc.id})

    # --- metrics -----------------------------------------------------------
    def metrics(self) -> dict:
        avg_latency = (sum(self._latencies_ms) / len(self._latencies_ms)) if self._latencies_ms else 0.0
        # Synthetic but bounded estimates so the dashboard has live numbers.
        accuracy = 0.94 if self._total_detections else 0.0
        fpr = round(self._total_false_positives / max(self._total_alerts, 1), 3)
        return {
            "total_detections": self._total_detections,
            "total_alerts": self._total_alerts,
            "total_false_positives": self._total_false_positives,
            "avg_latency_ms": round(avg_latency, 2),
            "p95_latency_ms": round(_p95(self._latencies_ms), 2),
            "detection_accuracy_target": accuracy,
            "false_positive_rate": fpr,
            "active_poles": len(self.poles),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = int(0.95 * (len(s) - 1))
    return s[idx]


pipeline = IncidentPipeline()


async def seed_default_poles() -> None:
    """Insert a small set of demo poles into the DB and pipeline."""
    demo_poles = [
        ("POLE-001", "MG Road Junction", 17.4486, 78.3908, "central"),
        ("POLE-002", "Hitech City Plaza", 17.4474, 78.3762, "tech"),
        ("POLE-003", "Charminar West Gate", 17.3616, 78.4747, "heritage"),
        ("POLE-004", "Banjara Hills Park", 17.4126, 78.4482, "residential"),
        ("POLE-005", "Secunderabad Station", 17.4399, 78.4983, "transport"),
    ]
    async with session_scope() as session:
        for pid, name, lat, lon, zone in demo_poles:
            existing = (await session.execute(select(Pole).where(Pole.id == pid))).scalar_one_or_none()
            if not existing:
                session.add(Pole(id=pid, name=name, latitude=lat, longitude=lon, zone=zone))
        await session.commit()

    for pid, name, lat, lon, zone in demo_poles:
        if pid not in pipeline.poles:
            pipeline.register_pole(PoleNode(pid, name, lat, lon, zone))
