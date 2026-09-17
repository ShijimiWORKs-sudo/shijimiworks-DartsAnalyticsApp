"""Named-landmark subset of BlazePose's 33-point topology (docs §13 特徴量:
head/shoulder/elbow/wrist/hip/knee/ankle). Index values are MediaPipe's
standard PoseLandmarker output ordering — see
https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker for
the full 33-point map; only the subset the spec asks for is named here.

Hand/wrist *rotation* (手首角度 in the fuller sense) and finger-level detail
are out of scope for the body PoseLandmarker model — that needs a hand
landmark model, not implemented in this phase (see phase5_notes.md).
"""

from __future__ import annotations

from dataclasses import dataclass

NAMED_LANDMARK_INDEX: dict[str, int] = {
    "nose": 0,  # stand-in for "head" position
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
}


@dataclass(frozen=True)
class LandmarkPoint:
    x: float  # normalized [0, 1], image-relative (MediaPipe convention)
    y: float
    confidence: float  # from the model's per-landmark visibility score, clamped [0, 1]

    def as_xy(self) -> tuple[float, float]:
        return (self.x, self.y)

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "confidence": self.confidence}


@dataclass(frozen=True)
class PoseFrame:
    points: dict[str, LandmarkPoint]

    def get(self, name: str) -> LandmarkPoint | None:
        return self.points.get(name)

    def to_dict(self) -> dict:
        return {name: p.to_dict() for name, p in self.points.items()}
