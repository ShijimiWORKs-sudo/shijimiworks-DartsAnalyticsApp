"""Named-landmark topology for MediaPipe's HandLandmarker (21-point,
Tasks API) — used for grip analysis (docs §Phase6, §8 グリップ写真).

Index values are MediaPipe's standard HandLandmarker output ordering —
see https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker
for the full 21-point map.
"""

from __future__ import annotations

from dataclasses import dataclass

NAMED_LANDMARK_INDEX: dict[str, int] = {
    "wrist": 0,
    "thumb_cmc": 1,
    "thumb_mcp": 2,
    "thumb_ip": 3,
    "thumb_tip": 4,
    "index_mcp": 5,
    "index_pip": 6,
    "index_dip": 7,
    "index_tip": 8,
    "middle_mcp": 9,
    "middle_pip": 10,
    "middle_dip": 11,
    "middle_tip": 12,
    "ring_mcp": 13,
    "ring_pip": 14,
    "ring_dip": 15,
    "ring_tip": 16,
    "pinky_mcp": 17,
    "pinky_pip": 18,
    "pinky_dip": 19,
    "pinky_tip": 20,
}


@dataclass(frozen=True)
class HandLandmarkPoint:
    x: float  # normalized [0, 1], image-relative (MediaPipe convention)
    y: float
    confidence: float  # see landmarker.py: HandLandmarker only exposes a
    # per-hand (handedness) confidence, not per-landmark visibility like
    # PoseLandmarker — this value is that same score applied uniformly to
    # every landmark in the frame. Coarser than Phase 5's pose confidence;
    # documented, not silently assumed.

    def as_xy(self) -> tuple[float, float]:
        return (self.x, self.y)

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "confidence": self.confidence}


@dataclass(frozen=True)
class HandFrame:
    points: dict[str, HandLandmarkPoint]
    handedness: str | None = None  # "Left" / "Right" per the model's own classification, or None if unavailable

    def get(self, name: str) -> HandLandmarkPoint | None:
        return self.points.get(name)

    def to_dict(self) -> dict:
        return {
            "points": {name: p.to_dict() for name, p in self.points.items()},
            "handedness": self.handedness,
        }
