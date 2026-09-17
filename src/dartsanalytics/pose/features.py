"""Derived pose features from a single PoseFrame (docs §13).

Every value here is DataKind.ESTIMATED (derived from an already-estimated
pose landmark) and carries a confidence — computed conservatively as the
minimum confidence among the landmarks a feature depends on, so a feature
is never reported more confidently than its shakiest input. This is a
documented combination rule, not a statistically rigorous one (see
docs/codex/reports/phase5_notes.md).

Only body_tilt / shoulder_tilt / hip_tilt / elbow_angle (both sides) are
computed here. Wrist rotation and knee/ankle angles are NOT computed in
this pass — not because they're impossible, but because scoping Phase 5 to
a smaller, well-tested set of features beat rushing every feature in
docs §13 at lower quality (see AGENTS.md "最小変更"; this is an
intentionally incremental first cut, not the full feature set).
"""

from __future__ import annotations

from dataclasses import dataclass

from dartsanalytics.common.enums import DataKind
from dartsanalytics.pose.geometry import joint_angle_deg, midpoint, tilt_from_horizontal_deg, tilt_from_vertical_deg
from dartsanalytics.pose.landmarks import PoseFrame


@dataclass(frozen=True)
class FeatureValue:
    value: float
    confidence: float
    data_kind: DataKind = DataKind.ESTIMATED

    def to_dict(self) -> dict:
        return {"value": self.value, "confidence": self.confidence, "data_kind": self.data_kind.value}


@dataclass(frozen=True)
class PoseFeatures:
    body_tilt_deg: FeatureValue | None
    shoulder_tilt_deg: FeatureValue | None
    hip_tilt_deg: FeatureValue | None
    left_elbow_angle_deg: FeatureValue | None
    right_elbow_angle_deg: FeatureValue | None

    def to_dict(self) -> dict:
        return {
            name: (value.to_dict() if value is not None else None)
            for name, value in (
                ("body_tilt_deg", self.body_tilt_deg),
                ("shoulder_tilt_deg", self.shoulder_tilt_deg),
                ("hip_tilt_deg", self.hip_tilt_deg),
                ("left_elbow_angle_deg", self.left_elbow_angle_deg),
                ("right_elbow_angle_deg", self.right_elbow_angle_deg),
            )
        }


def _min_confidence(*confidences: float) -> float:
    return min(confidences)


def _elbow_angle(frame: PoseFrame, side: str) -> FeatureValue | None:
    shoulder = frame.get(f"{side}_shoulder")
    elbow = frame.get(f"{side}_elbow")
    wrist = frame.get(f"{side}_wrist")
    if not (shoulder and elbow and wrist):
        return None
    try:
        angle = joint_angle_deg(shoulder.as_xy(), elbow.as_xy(), wrist.as_xy())
    except ValueError:
        return None
    return FeatureValue(value=angle, confidence=_min_confidence(shoulder.confidence, elbow.confidence, wrist.confidence))


def compute_pose_features(frame: PoseFrame) -> PoseFeatures:
    left_shoulder, right_shoulder = frame.get("left_shoulder"), frame.get("right_shoulder")
    left_hip, right_hip = frame.get("left_hip"), frame.get("right_hip")

    body_tilt: FeatureValue | None = None
    if left_shoulder and right_shoulder and left_hip and right_hip:
        mid_shoulder = midpoint(left_shoulder.as_xy(), right_shoulder.as_xy())
        mid_hip = midpoint(left_hip.as_xy(), right_hip.as_xy())
        try:
            angle = tilt_from_vertical_deg(bottom=mid_hip, top=mid_shoulder)
            body_tilt = FeatureValue(
                value=angle,
                confidence=_min_confidence(
                    left_shoulder.confidence, right_shoulder.confidence, left_hip.confidence, right_hip.confidence
                ),
            )
        except ValueError:
            body_tilt = None

    shoulder_tilt: FeatureValue | None = None
    if left_shoulder and right_shoulder:
        try:
            angle = tilt_from_horizontal_deg(left_shoulder.as_xy(), right_shoulder.as_xy())
            shoulder_tilt = FeatureValue(
                value=angle, confidence=_min_confidence(left_shoulder.confidence, right_shoulder.confidence)
            )
        except ValueError:
            shoulder_tilt = None

    hip_tilt: FeatureValue | None = None
    if left_hip and right_hip:
        try:
            angle = tilt_from_horizontal_deg(left_hip.as_xy(), right_hip.as_xy())
            hip_tilt = FeatureValue(value=angle, confidence=_min_confidence(left_hip.confidence, right_hip.confidence))
        except ValueError:
            hip_tilt = None

    return PoseFeatures(
        body_tilt_deg=body_tilt,
        shoulder_tilt_deg=shoulder_tilt,
        hip_tilt_deg=hip_tilt,
        left_elbow_angle_deg=_elbow_angle(frame, "left"),
        right_elbow_angle_deg=_elbow_angle(frame, "right"),
    )
