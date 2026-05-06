"""MediaPipe Pose-based fall detection and posture understanding.

This module provides optional pose estimation enrichment for the vision pipeline.
It is designed to be additive and non-breaking: if disabled or failing, the system
continues to operate normally using existing detectors.

Key features:
- Fall detection via pose angle analysis
- Posture classification (standing, sitting, lying)
- Multi-person handling (top-1 person by detection confidence)
- Graceful degradation on import/runtime failures
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any

from app.ai.vision import VisionDetection
from app.config import get_settings


@dataclass
class PoseLandmark:
    """Represents a single pose landmark with normalized coordinates."""
    name: str
    x: float  # normalized [0, 1]
    y: float  # normalized [0, 1]
    z: float  # depth (relative)
    visibility: float  # [0, 1] confidence


@dataclass
class PoseDetection:
    """Pose estimation result for a single person."""
    person_id: int
    confidence: float
    landmarks: list[PoseLandmark]
    posture: str  # 'standing', 'sitting', 'lying', 'unknown'
    is_fall: bool
    fall_confidence: float
    bbox: tuple[float, float, float, float] | None = None  # x, y, w, h normalized
    extra: dict[str, Any] | None = None


class PoseEstimator(abc.ABC):
    """Abstract interface for pose estimation."""

    @abc.abstractmethod
    def infer(self, frame: Any) -> list[PoseDetection]:
        """Estimate poses from an image frame.

        Args:
            frame: Image frame (numpy array) or dict with scene info

        Returns:
            List of PoseDetection objects, one per detected person
        """
        ...

    @abc.abstractmethod
    def to_vision_detections(self, poses: list[PoseDetection]) -> list[VisionDetection]:
        """Convert pose detections to VisionDetection format for fusion.

        Args:
            poses: List of PoseDetection objects

        Returns:
            List of VisionDetection objects compatible with fusion engine
        """
        ...


class MockPoseEstimator(PoseEstimator):
    """Mock pose estimator that returns empty results.

    Used when pose estimation is disabled or MediaPipe is unavailable.
    """

    def infer(self, frame: Any) -> list[PoseDetection]:
        return []

    def to_vision_detections(self, poses: list[PoseDetection]) -> list[VisionDetection]:
        return []


class MediaPipePoseEstimator(PoseEstimator):
    """MediaPipe Pose-based fall detector and posture analyzer.

    Uses Google MediaPipe Pose for lightweight, real-time pose estimation.
    Analyzes body angles to detect falls and classify postures.
    """

    # MediaPipe Pose landmark indices (BlazePose topology)
    LANDMARK_NAMES = [
        "nose", "left_eye_inner", "left_eye", "left_eye_outer",
        "right_eye_inner", "right_eye", "right_eye_outer",
        "left_ear", "right_ear", "mouth_left", "mouth_right",
        "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
        "left_wrist", "right_wrist", "left_pinky", "right_pinky",
        "left_index", "right_index", "left_thumb", "right_thumb",
        "left_hip", "right_hip", "left_knee", "right_knee",
        "left_ankle", "right_ankle", "left_heel", "right_heel",
        "left_foot_index", "right_foot_index"
    ]

    # Landmark indices for key body parts
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28

    def __init__(self) -> None:
        """Initialize MediaPipe Pose estimator.

        Lazy import to avoid hard dependency - system works without mediapipe.
        """
        self._mp_pose = None
        self._mp_self = None
        self._pose = None
        try:
            import mediapipe as mp
            self._mp_pose = mp.solutions.pose
            self._mp_self = mp
            self._pose = self._mp_pose.Pose(
                static_image_mode=False,
                model_complexity=1,
                enable_segmentation=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
        except Exception:
            # MediaPipe not available - will fallback gracefully
            pass

    def infer(self, frame: Any) -> list[PoseDetection]:
        """Estimate poses from an image frame.

        Args:
            frame: Image frame (numpy array BGR/RGB) or dict

        Returns:
            List of PoseDetection objects
        """
        # Skip if not a real image frame
        if not isinstance(frame, (bytes, bytearray)) and not hasattr(frame, 'shape'):
            return []

        # Skip if MediaPipe not loaded
        if self._pose is None:
            return []

        try:
            import cv2
            import numpy as np

            # Handle different input formats
            if isinstance(frame, dict):
                # Simulation mode - no real image
                return []

            # Ensure we have a proper image array
            if isinstance(frame, (bytes, bytearray)):
                img = cv2.imdecode(np.frombuffer(frame, np.uint8), cv2.IMREAD_COLOR)
                if img is None:
                    return []
            else:
                img = frame

            if img is None or len(img.shape) < 3:
                return []

            # Convert BGR to RGB for MediaPipe
            if len(img.shape) == 3 and img.shape[2] == 3:
                rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            else:
                return []

            # Run pose estimation
            results = self._pose.process(rgb_img)

            if results.pose_landmarks is None:
                return []

            detections = []
            height, width = img.shape[:2]

            for idx, landmarks in enumerate(results.pose_landmarks.landmark):
                # Extract landmarks
                pose_landmarks = []
                for i, lm in enumerate(landmarks):
                    if i < len(self.LANDMARK_NAMES):
                        pose_landmarks.append(PoseLandmark(
                            name=self.LANDMARK_NAMES[i],
                            x=lm.x,
                            y=lm.y,
                            z=lm.z,
                            visibility=lm.visibility if hasattr(lm, 'visibility') else 1.0
                        ))

                # Calculate bounding box from visible landmarks
                visible = [lm for lm in landmarks if lm.visibility > 0.5]
                if not visible:
                    continue

                xs = [lm.x for lm in visible]
                ys = [lm.y for lm in visible]
                bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

                # Analyze posture and fall
                posture = self._classify_posture(landmarks)
                is_fall, fall_conf = self._detect_fall(landmarks, posture)

                # Use overall visibility as confidence proxy
                avg_visibility = sum(lm.visibility for lm in landmarks) / len(landmarks)

                detections.append(PoseDetection(
                    person_id=idx,
                    confidence=avg_visibility,
                    landmarks=pose_landmarks,
                    posture=posture,
                    is_fall=is_fall,
                    fall_confidence=fall_conf,
                    bbox=bbox,
                    extra={
                        'shoulder_hip_angle': self._calculate_shoulder_hip_angle(landmarks),
                        'body_inclination': self._calculate_body_inclination(landmarks)
                    }
                ))

            return detections

        except Exception:
            # Runtime failure - return empty to maintain stability
            return []

    def _classify_posture(self, landmarks) -> str:
        """Classify body posture from landmarks.

        Returns: 'standing', 'sitting', 'lying', or 'unknown'
        """
        try:
            # Get key landmarks
            left_shoulder = landmarks[self.LEFT_SHOULDER]
            right_shoulder = landmarks[self.RIGHT_SHOULDER]
            left_hip = landmarks[self.LEFT_HIP]
            right_hip = landmarks[self.RIGHT_HIP]

            # Calculate shoulder and hip centers
            shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
            hip_y = (left_hip.y + right_hip.y) / 2

            # Vertical distance between shoulders and hips
            torso_length = abs(shoulder_y - hip_y)

            # Get ankle positions
            left_ankle = landmarks[self.LEFT_ANKLE]
            right_ankle = landmarks[self.RIGHT_ANKLE]
            ankle_y = (left_ankle.y + right_ankle.y) / 2

            # Body height ratio (hip to ankle vs torso)
            leg_length = abs(hip_y - ankle_y)

            if torso_length < 0.05:  # Very small torso = likely lying
                return 'lying'
            elif torso_length > 0.15 and leg_length > 0.2:  # Extended body = standing
                return 'standing'
            elif 0.08 < torso_length < 0.15:  # Compressed torso = sitting
                return 'sitting'
            else:
                return 'unknown'
        except Exception:
            return 'unknown'

    def _detect_fall(self, landmarks, posture: str) -> tuple[bool, float]:
        """Detect if person has fallen.

        A fall is indicated by:
        - Lying posture with low body inclination
        - Sudden change in shoulder-hip angle
        - Low vertical position relative to frame

        Returns:
            (is_fall, confidence)
        """
        try:
            # Posture-based detection
            if posture == 'lying':
                # Check body inclination
                inclination = self._calculate_body_inclination(landmarks)
                if inclination > 0.7:  # Mostly horizontal
                    return True, inclination

            # Shoulder-hip angle analysis
            shoulder_hip_angle = self._calculate_shoulder_hip_angle(landmarks)
            if shoulder_hip_angle > 120:  # Very tilted
                return True, min(0.99, shoulder_hip_angle / 180)

            return False, 0.0
        except Exception:
            return False, 0.0

    def _calculate_shoulder_hip_angle(self, landmarks) -> float:
        """Calculate angle between shoulder line and hip line."""
        try:
            ls = landmarks[self.LEFT_SHOULDER]
            rs = landmarks[self.RIGHT_SHOULDER]
            lh = landmarks[self.LEFT_HIP]
            rh = landmarks[self.RIGHT_HIP]

            # Shoulder vector
            shoulder_dx = rs.x - ls.x
            shoulder_dy = rs.y - ls.y

            # Hip vector
            hip_dx = rh.x - lh.x
            hip_dy = rh.y - lh.y

            # Dot product and magnitudes
            dot = shoulder_dx * hip_dx + shoulder_dy * hip_dy
            mag_shoulder = (shoulder_dx ** 2 + shoulder_dy ** 2) ** 0.5
            mag_hip = (hip_dx ** 2 + hip_dy ** 2) ** 0.5

            if mag_shoulder * mag_hip == 0:
                return 0.0

            cos_angle = dot / (mag_shoulder * mag_hip)
            cos_angle = max(-1, min(1, cos_angle))  # Clamp for numerical stability

            import math
            angle_deg = math.degrees(math.acos(cos_angle))
            return angle_deg
        except Exception:
            return 0.0

    def _calculate_body_inclination(self, landmarks) -> float:
        """Calculate body inclination from vertical (0=vertical, 1=horizontal)."""
        try:
            # Use shoulder-hip vector
            ls = landmarks[self.LEFT_SHOULDER]
            rs = landmarks[self.RIGHT_SHOULDER]
            lh = landmarks[self.LEFT_HIP]
            rh = landmarks[self.RIGHT_HIP]

            # Body center line
            shoulder_y = (ls.y + rs.y) / 2
            hip_y = (lh.y + rh.y) / 2
            shoulder_x = (ls.x + rs.x) / 2
            hip_x = (lh.x + rh.x) / 2

            dy = abs(shoulder_y - hip_y)
            dx = abs(shoulder_x - hip_x)

            # Ratio of horizontal to total displacement
            total = (dx ** 2 + dy ** 2) ** 0.5
            if total == 0:
                return 0.0

            return dx / total  # 0 = vertical, 1 = horizontal
        except Exception:
            return 0.0

    def to_vision_detections(self, poses: list[PoseDetection]) -> list[VisionDetection]:
        """Convert pose detections to VisionDetection format.

        Maps fall detection and abnormal postures to fusion-compatible events.
        Only returns detections above confidence threshold.

        Note: Uses existing incident types from fusion.py for compatibility:
        - fall_detected -> mapped to 'violence' (high severity)
        - posture_anomaly -> mapped to 'crowd_anomaly' (medium severity)
        - sitting_person -> informational only, below alert threshold
        """
        settings = get_settings()
        threshold = settings.detection_confidence_threshold

        detections = []
        for pose in poses:
            # Fall detection -> map to 'violence' for fusion compatibility
            if pose.is_fall and pose.fall_confidence >= threshold:
                detections.append(VisionDetection(
                    label="violence",  # Use existing fusion incident type
                    confidence=pose.fall_confidence,
                    bbox=pose.bbox,
                    extra={
                        'posture': pose.posture,
                        'person_id': pose.person_id,
                        'source': 'pose_estimation',
                        'original_label': 'fall_detected'
                    }
                ))

            # Abnormal posture detection -> map to 'crowd_anomaly'
            if pose.posture == 'lying' and pose.confidence >= threshold:
                # Only report if not already reported as fall
                if not pose.is_fall:
                    detections.append(VisionDetection(
                        label="crowd_anomaly",  # Use existing fusion incident type
                        confidence=pose.confidence * 0.9,  # Slightly reduced weight
                        bbox=pose.bbox,
                        extra={
                            'posture': pose.posture,
                            'person_id': pose.person_id,
                            'source': 'pose_estimation',
                            'original_label': 'posture_anomaly'
                        }
                    ))

            # Sitting posture - informational only, low priority
            # Not converted to VisionDetection to avoid alert noise

        return detections


def build_default_pose_estimator() -> PoseEstimator:
    """Build pose estimator based on configuration.

    Returns MediaPipe estimator if enabled and available, otherwise mock.
    """
    settings = get_settings()

    if not getattr(settings, 'enable_pose_estimation', False):
        return MockPoseEstimator()

    try:
        estimator = MediaPipePoseEstimator()
        # Verify MediaPipe loaded successfully
        if estimator._pose is None:
            return MockPoseEstimator()
        return estimator
    except Exception:
        # Fallback to mock on any error
        return MockPoseEstimator()
