"""Multi-modal threat fusion.

Combines vision + audio + motion + panic button signals into a single
threat score per pole per tick. Above ``fusion_alert_threshold`` -> alert.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.audio import AudioPrediction
from app.ai.vision import VisionDetection
from app.config import get_settings

# Maps individual evidence labels to canonical incident types and severity.
INCIDENT_TYPES: dict[str, dict[str, Any]] = {
    "violence": {"severity": "high", "weight": 1.0},
    "intrusion": {"severity": "high", "weight": 0.85},
    "abandoned_object": {"severity": "medium", "weight": 0.6},
    "crowd_anomaly": {"severity": "medium", "weight": 0.55},
    "loitering": {"severity": "low", "weight": 0.4},
    "scream": {"severity": "high", "weight": 0.95},
    "gunshot": {"severity": "critical", "weight": 1.0},
    "glass_break": {"severity": "medium", "weight": 0.7},
    "distress": {"severity": "medium", "weight": 0.55},
    "panic_sos": {"severity": "critical", "weight": 1.0},
    "motion_burst": {"severity": "low", "weight": 0.3},
}


@dataclass
class FusedThreat:
    incident_type: str
    score: float
    severity: str
    sources: dict[str, float] = field(default_factory=dict)
    description: str = ""
    pose_boost: float = 0.0  # Optional pose-derived score adjustment
    pose_tags: list[str] = field(default_factory=list)  # Tags for pose adjustments


class FusionEngine:
    """Late-fusion combiner with type-aware aggregation."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def fuse(
        self,
        *,
        vision: list[VisionDetection],
        audio: list[AudioPrediction],
        motion_payload: dict | None,
        panic_payload: dict | None,
        pose_adjustments: dict[str, dict[str, Any]] | None = None,
    ) -> list[FusedThreat]:
        # Aggregate per-label confidence from each modality.
        evidence: dict[str, dict[str, float]] = {}

        for d in vision:
            if d.confidence < self.settings.detection_confidence_threshold:
                continue
            evidence.setdefault(d.label, {})["vision"] = max(
                evidence.get(d.label, {}).get("vision", 0.0), d.confidence
            )

        for a in audio:
            if a.confidence < self.settings.detection_confidence_threshold:
                continue
            evidence.setdefault(a.label, {})["audio"] = max(
                evidence.get(a.label, {}).get("audio", 0.0), a.confidence
            )

        if motion_payload and motion_payload.get("triggered"):
            v = float(motion_payload.get("velocity_mps", 0.0))
            if v > 0.6:
                evidence.setdefault("motion_burst", {})["motion"] = min(0.85, 0.4 + v / 2)

        if panic_payload and panic_payload.get("pressed"):
            evidence["panic_sos"] = {"panic_button": 1.0}

        # Co-occurrence boosts: violence + scream / gunshot fuses to a stronger score.
        if "violence" in evidence and ("scream" in evidence or "gunshot" in evidence):
            evidence["violence"]["audio_corroboration"] = 0.95

        threats: list[FusedThreat] = []
        for label, sources in evidence.items():
            meta = INCIDENT_TYPES.get(label)
            if not meta:
                continue
            score = self._aggregate(sources, meta["weight"])
            if score < self.settings.fusion_alert_threshold and label != "panic_sos":
                continue
            
            # Apply pose-based score adjustments if available
            pose_boost = 0.0
            pose_tags: list[str] = []
            if pose_adjustments and label in pose_adjustments:
                adj = pose_adjustments[label]
                pose_boost = adj.get("boost", 0.0)
                if "tag" in adj:
                    pose_tags = [adj["tag"]]
                score = min(0.99, score + pose_boost)
            
            description = self._describe(label, sources)
            if pose_boost > 0:
                description += f" [pose-adjusted +{pose_boost:.2f}]"
            
            threats.append(
                FusedThreat(
                    incident_type=label,
                    score=round(score, 3),
                    severity=meta["severity"],
                    sources={k: round(v, 3) for k, v in sources.items()},
                    description=description,
                    pose_boost=round(pose_boost, 3),
                    pose_tags=pose_tags,
                )
            )
        return threats

    @staticmethod
    def _aggregate(sources: dict[str, float], weight: float) -> float:
        # Probabilistic OR over sources, scaled by class weight.
        prob = 1.0
        for v in sources.values():
            prob *= (1.0 - max(0.0, min(1.0, v)))
        combined = 1.0 - prob
        return min(0.99, combined * (0.6 + 0.4 * weight))

    @staticmethod
    def _describe(label: str, sources: dict[str, float]) -> str:
        src_str = ", ".join(f"{k}={v:.2f}" for k, v in sources.items())
        return f"{label.replace('_', ' ').title()} detected via {src_str}"
