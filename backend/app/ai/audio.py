"""Audio event classifier.

MVP uses a rule-based classifier mapping simulated event labels to threat
classes with calibrated confidences. Architecture supports plugging in a
trained CNN (e.g. PANNs/YAMNet) by replacing ``AudioClassifier.infer``.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class AudioPrediction:
    label: str
    confidence: float


class AudioClassifier(abc.ABC):
    @abc.abstractmethod
    def infer(self, reading_payload: dict) -> list[AudioPrediction]:
        ...


class RuleBasedAudioClassifier(AudioClassifier):
    LABEL_MAP = {
        "scream": ("scream", 0.85),
        "gunshot": ("gunshot", 0.92),
        "glass_break": ("glass_break", 0.78),
        "shouting": ("distress", 0.62),
    }

    def infer(self, reading_payload: dict) -> list[AudioPrediction]:
        label = reading_payload.get("event_label", "ambient")
        db = float(reading_payload.get("db_level", 0))
        if label in self.LABEL_MAP:
            base_label, base_conf = self.LABEL_MAP[label]
            # boost confidence slightly with loudness
            conf = min(0.99, base_conf + max(0.0, (db - 70) / 200))
            return [AudioPrediction(label=base_label, confidence=round(conf, 3))]
        return []


def build_default_audio_classifier() -> AudioClassifier:
    return RuleBasedAudioClassifier()
