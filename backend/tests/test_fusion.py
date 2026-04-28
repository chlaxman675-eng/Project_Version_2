"""Tests for the multi-modal fusion engine."""
from __future__ import annotations

from app.ai.audio import AudioPrediction
from app.ai.fusion import FusionEngine
from app.ai.vision import VisionDetection


def test_fusion_low_evidence_no_alerts():
    fe = FusionEngine()
    threats = fe.fuse(vision=[], audio=[], motion_payload=None, panic_payload=None)
    assert threats == []


def test_fusion_violence_triggers():
    fe = FusionEngine()
    threats = fe.fuse(
        vision=[VisionDetection("violence", 0.9)],
        audio=[AudioPrediction("scream", 0.85)],
        motion_payload={"triggered": True, "velocity_mps": 1.0},
        panic_payload=None,
    )
    types = {t.incident_type for t in threats}
    assert "violence" in types
    violence = next(t for t in threats if t.incident_type == "violence")
    assert violence.severity == "high"
    assert violence.score >= 0.65


def test_panic_always_alerts():
    fe = FusionEngine()
    threats = fe.fuse(
        vision=[], audio=[],
        motion_payload=None,
        panic_payload={"pressed": True, "reporter": "alice"},
    )
    types = [t.incident_type for t in threats]
    assert "panic_sos" in types


def test_gunshot_critical():
    fe = FusionEngine()
    threats = fe.fuse(
        vision=[], audio=[AudioPrediction("gunshot", 0.95)],
        motion_payload=None, panic_payload=None,
    )
    gun = next(t for t in threats if t.incident_type == "gunshot")
    assert gun.severity == "critical"
