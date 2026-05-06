"""Pose-aware scoring module for behavior enhancement.

This module provides additive scoring adjustments based on pose data.
It is designed to be non-breaking: if disabled or failing, the system
continues to operate normally using existing fusion logic.

Key features:
- Temporal smoothing (requires 2-3 consecutive detections)
- Confidence thresholding
- Score boost capping to prevent double-counting
- Top-1 person aggregation for multi-person handling
- Structured logging for debugging
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from app.ai.pose import PoseDetection
from app.config import get_settings


@dataclass
class TemporalState:
    """Tracks temporal state for a specific detection type at a location."""
    consecutive_count: int = 0
    last_seen_at: float = 0.0
    accumulated_boost: float = 0.0
    tags: set[str] = field(default_factory=set)


class PoseScoreAdjuster:
    """Applies pose-based score adjustments with temporal smoothing.
    
    This class provides conservative score boosts based on pose detections:
    - Fall detection: +0.20 boost to distress incidents
    - Lying posture: +0.15 boost to crowd_anomaly incidents
    
    All adjustments are capped and require temporal confirmation.
    """
    
    # Configuration constants
    MIN_CONSECUTIVE_TICKS = 2  # Require 2 consecutive detections
    MAX_TIME_GAP_SECONDS = 4.0  # Reset if gap exceeds this
    MAX_BOOST_CAP = 0.25  # Maximum total boost per incident type
    POSE_CONFIDENCE_THRESHOLD = 0.6  # Minimum pose confidence
    
    # Boost values per event type
    FALL_BOOST = 0.20
    LYING_BOOST = 0.15
    
    def __init__(self) -> None:
        """Initialize the pose score adjuster."""
        self.settings = get_settings()
        # Track temporal state per (pole_id, incident_type)
        self._temporal_state: dict[tuple[str, str], TemporalState] = defaultdict(TemporalState)
        self._last_cleanup = time.time()
        
    def compute_adjustments(
        self,
        pole_id: str,
        pose_detections: list[PoseDetection],
        current_time: float | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Compute score adjustments based on pose detections.
        
        Args:
            pole_id: Identifier for the pole/location
            pose_detections: List of pose detections from current tick
            current_time: Optional timestamp (defaults to time.time())
            
        Returns:
            Dictionary mapping incident_type to adjustment info:
            {
                "distress": {"boost": 0.20, "reason": "fall_detected", "tag": "pose_fall_001"},
                "crowd_anomaly": {"boost": 0.15, "reason": "lying_posture", "tag": "pose_lying_001"}
            }
        """
        if current_time is None:
            current_time = time.time()
            
        # Periodic cleanup of stale states
        if current_time - self._last_cleanup > 60.0:
            self._cleanup_stale_states(current_time)
            self._last_cleanup = current_time
        
        adjustments: dict[str, dict[str, Any]] = {}
        
        # Skip if no pose estimation enabled
        if not self.settings.enable_pose_estimation:
            return adjustments
        
        # Skip if no detections
        if not pose_detections:
            # Reset temporal state for all types at this pole
            self._reset_temporal_state(pole_id, "distress")
            self._reset_temporal_state(pole_id, "crowd_anomaly")
            return adjustments
        
        # Handle multiple persons: use top-1 by confidence (no summation)
        top_person = max(pose_detections, key=lambda p: p.confidence)
        
        # Check for fall detection
        if top_person.is_fall and top_person.fall_confidence >= self.POSE_CONFIDENCE_THRESHOLD:
            boost_info = self._apply_temporal_boost(
                pole_id=pole_id,
                incident_type="distress",
                boost_value=self.FALL_BOOST,
                reason="fall_detected",
                confidence=top_person.fall_confidence,
                current_time=current_time,
            )
            if boost_info:
                adjustments["distress"] = boost_info
                logger.info(
                    "pose_score_adjustment",
                    pole_id=pole_id,
                    incident_type="distress",
                    boost=boost_info["boost"],
                    reason=boost_info["reason"],
                    tag=boost_info["tag"],
                    confidence=boost_info.get("confidence", 0.0),
                )
        
        # Check for lying posture (only if not already a fall)
        elif top_person.posture == "lying" and top_person.confidence >= self.POSE_CONFIDENCE_THRESHOLD:
            boost_info = self._apply_temporal_boost(
                pole_id=pole_id,
                incident_type="crowd_anomaly",
                boost_value=self.LYING_BOOST,
                reason="lying_posture",
                confidence=top_person.confidence,
                current_time=current_time,
            )
            if boost_info:
                adjustments["crowd_anomaly"] = boost_info
                logger.info(
                    "pose_score_adjustment",
                    pole_id=pole_id,
                    incident_type="crowd_anomaly",
                    boost=boost_info["boost"],
                    reason=boost_info["reason"],
                    tag=boost_info["tag"],
                    confidence=boost_info.get("confidence", 0.0),
                )
        
        return adjustments
    
    def _apply_temporal_boost(
        self,
        pole_id: str,
        incident_type: str,
        boost_value: float,
        reason: str,
        confidence: float,
        current_time: float,
    ) -> dict[str, Any] | None:
        """Apply temporal smoothing to determine if boost should be applied.
        
        Returns adjustment info if threshold met, None otherwise.
        """
        state_key = (pole_id, incident_type)
        state = self._temporal_state[state_key]
        
        # Check time gap - reset if too long
        if state.last_seen_at > 0 and (current_time - state.last_seen_at) > self.MAX_TIME_GAP_SECONDS:
            logger.debug(
                "pose_temporal_reset",
                pole_id=pole_id,
                incident_type=incident_type,
                reason="time_gap_exceeded",
                gap_seconds=current_time - state.last_seen_at,
            )
            state.consecutive_count = 0
            state.accumulated_boost = 0.0
        
        # Update state
        state.last_seen_at = current_time
        state.consecutive_count += 1
        
        # Generate unique tag for this detection sequence
        if not state.tags or len(state.tags) == 0:
            base_tag = f"pose_{reason.split('_')[0]}_{pole_id.replace('-', '_')}"
            state.tags.add(base_tag)
        
        # Cap accumulated boost
        new_accumulated = min(state.accumulated_boost + boost_value, self.MAX_BOOST_CAP)
        
        # Only apply boost after minimum consecutive ticks
        if state.consecutive_count < self.MIN_CONSECUTIVE_TICKS:
            logger.debug(
                "pose_temporal_waiting",
                pole_id=pole_id,
                incident_type=incident_type,
                consecutive_count=state.consecutive_count,
                required=self.MIN_CONSECUTIVE_TICKS,
            )
            state.accumulated_boost = new_accumulated
            return None
        
        # Calculate actual boost to apply (delta from previous)
        actual_boost = new_accumulated - state.accumulated_boost
        state.accumulated_boost = new_accumulated
        
        # Get tag for logging
        tag = next(iter(state.tags)) if state.tags else f"pose_{reason}_{pole_id}"
        
        return {
            "boost": round(actual_boost, 3),
            "reason": reason,
            "tag": tag,
            "confidence": round(confidence, 3),
            "consecutive_count": state.consecutive_count,
            "capped": new_accumulated >= self.MAX_BOOST_CAP,
        }
    
    def _reset_temporal_state(self, pole_id: str, incident_type: str) -> None:
        """Reset temporal state for a specific pole/incident combination."""
        state_key = (pole_id, incident_type)
        if state_key in self._temporal_state:
            state = self._temporal_state[state_key]
            if state.consecutive_count > 0:
                logger.debug(
                    "pose_temporal_reset",
                    pole_id=pole_id,
                    incident_type=incident_type,
                    reason="no_detection",
                    final_consecutive_count=state.consecutive_count,
                )
            state.consecutive_count = 0
            state.accumulated_boost = 0.0
            state.tags.clear()
    
    def _cleanup_stale_states(self, current_time: float) -> None:
        """Remove stale temporal states to prevent memory growth."""
        stale_keys = []
        for key, state in self._temporal_state.items():
            if state.last_seen_at > 0 and (current_time - state.last_seen_at) > 300.0:  # 5 minutes
                stale_keys.append(key)
        
        for key in stale_keys:
            del self._temporal_state[key]
        
        if stale_keys:
            logger.debug("pose_cleanup_removed_stale_states", count=len(stale_keys))
    
    def get_metrics(self) -> dict[str, Any]:
        """Return metrics about current temporal states."""
        active_states = sum(1 for s in self._temporal_state.values() if s.consecutive_count > 0)
        total_boost_applied = sum(s.accumulated_boost for s in self._temporal_state.values())
        
        return {
            "active_temporal_states": active_states,
            "total_accumulated_boost": round(total_boost_applied, 3),
            "tracked_pole_incident_pairs": len(self._temporal_state),
        }


# Singleton instance
_pose_adjuster: PoseScoreAdjuster | None = None


def get_pose_adjuster() -> PoseScoreAdjuster:
    """Get or create the singleton pose score adjuster."""
    global _pose_adjuster
    if _pose_adjuster is None:
        _pose_adjuster = PoseScoreAdjuster()
    return _pose_adjuster


def reset_pose_adjuster() -> None:
    """Reset the singleton (useful for testing)."""
    global _pose_adjuster
    _pose_adjuster = None
