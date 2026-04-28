"""Replayable demo scenarios.

Each scenario synthesises a multi-modal evidence bundle and pushes it through
the same fusion path as live sensor data, producing real DB-backed incidents
and dashboard alerts.
"""
from __future__ import annotations

import asyncio
import random
from typing import Any

from app.ai.audio import AudioPrediction
from app.ai.fusion import FusedThreat
from app.ai.vision import VisionDetection
from app.engine.event_bus import bus

SCENARIOS: dict[str, dict[str, Any]] = {
    "suspicious_loiterer": {
        "title": "Suspicious loiterer near ATM",
        "vision": [VisionDetection("loitering", 0.72, extra={"scene": "loitering"})],
        "audio": [],
        "motion": {"triggered": True, "velocity_mps": 0.8},
    },
    "violent_fight": {
        "title": "Street fight with shouting",
        "vision": [VisionDetection("violence", 0.88, extra={"scene": "fight"})],
        "audio": [AudioPrediction("scream", 0.84)],
        "motion": {"triggered": True, "velocity_mps": 1.2},
    },
    "gunshot": {
        "title": "Gunshot detected",
        "vision": [],
        "audio": [AudioPrediction("gunshot", 0.95)],
        "motion": {"triggered": True, "velocity_mps": 1.4},
    },
    "abandoned_object": {
        "title": "Abandoned bag at junction",
        "vision": [VisionDetection("abandoned_object", 0.81, extra={"scene": "abandoned_object"})],
        "audio": [],
        "motion": {"triggered": False},
    },
    "crowd_anomaly": {
        "title": "Sudden crowd swell",
        "vision": [VisionDetection("crowd_anomaly", 0.83, extra={"scene": "crowd_anomaly"})],
        "audio": [],
        "motion": {"triggered": True, "velocity_mps": 0.9},
    },
    "panic_button": {
        "title": "Citizen pressed panic button",
        "vision": [],
        "audio": [],
        "motion": {"triggered": False},
        "panic": True,
    },
    "intrusion": {
        "title": "Restricted-zone intrusion",
        "vision": [VisionDetection("intrusion", 0.79, extra={"scene": "intrusion"})],
        "audio": [],
        "motion": {"triggered": True, "velocity_mps": 0.7},
    },
}


def list_scenarios() -> list[dict]:
    return [{"id": k, "title": v["title"]} for k, v in SCENARIOS.items()]


async def inject_scenario(pipeline, scenario_id: str, *, pole_id: str | None = None) -> dict:
    if scenario_id not in SCENARIOS:
        return {"ok": False, "error": f"unknown scenario {scenario_id}"}

    spec = SCENARIOS[scenario_id]
    pole = None
    if pole_id and pole_id in pipeline.poles:
        pole = pipeline.poles[pole_id]
    elif pipeline.poles:
        pole = random.choice(list(pipeline.poles.values()))

    await bus.publish("simulation.injected", {
        "scenario": scenario_id, "title": spec["title"],
        "pole_id": pole.pole_id if pole else None,
    })

    if spec.get("panic"):
        # Materialise immediately so demo flows don't depend on the live tick loop.
        threat = FusedThreat(
            incident_type="panic_sos",
            score=1.0,
            severity="critical",
            sources={"panic_button": 1.0},
            description="Citizen pressed panic button (scenario)",
        )
        await pipeline._materialise_threat(  # noqa: SLF001
            pole=pole, threat=threat,
            latitude=pole.latitude if pole else None,
            longitude=pole.longitude if pole else None,
        )
        await asyncio.sleep(0)
        return {"ok": True, "scenario": scenario_id, "pole_id": pole.pole_id if pole else None}

    threats = pipeline.fusion.fuse(
        vision=spec.get("vision", []),
        audio=spec.get("audio", []),
        motion_payload=spec.get("motion"),
        panic_payload=None,
    )
    for threat in threats:
        await pipeline._materialise_threat(  # noqa: SLF001 - intentional reuse
            pole=pole, threat=threat,
            latitude=pole.latitude if pole else None,
            longitude=pole.longitude if pole else None,
        )

    return {
        "ok": True,
        "scenario": scenario_id,
        "pole_id": pole.pole_id if pole else None,
        "threats": [t.__dict__ for t in threats],
    }
