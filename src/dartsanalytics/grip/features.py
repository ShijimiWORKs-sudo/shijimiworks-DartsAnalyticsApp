"""Derived grip features from a single HandFrame (docs §Phase6, §8).

Docs §Phase6: "左右写真から、指位置・指の角度・バレル軸・手首角度を推定する。
2Dから接触圧などを断定しない。" This module computes:

- finger curl angles (thumb/index/middle, PIP-joint interior angle —
  same math shape as Phase 5's elbow angle: MCP-PIP-TIP)
- wrist_angle_deg: 2D orientation of the wrist->middle-finger-MCP line
  (a proxy for hand/wrist orientation in the image plane — not a true
  3D wrist rotation, which a single 2D photo cannot recover)
- barrel_axis_deg: a *geometric proxy* for barrel orientation, taken as
  the thumb-tip -> index-tip line. The actual dart barrel is never
  detected as an object in this phase, so this is explicitly weaker
  evidence than the finger/wrist angles above — its confidence is
  scaled down and hard-capped accordingly (see MAX_BARREL_AXIS_CONFIDENCE).

Explicitly NOT computed (docs §8: "2D画像だけで実際の接触圧や完全な3Dグリップ
を断定しない"): contact pressure, true 3D grip structure, and true
barrel geometry (see grip/analysis.py NOT_ASSESSED for the full list
surfaced to callers/reports).

Reuses the pure-math helpers from dartsanalytics.pose.geometry —
despite the module name, joint_angle_deg/tilt_from_horizontal_deg are
generic 2D geometry with no pose-specific coupling. Duplicating them
here would violate AGENTS.md's minimal-change / no-unrelated-refactor
rule while adding a maintenance-divergence risk between two copies of
the same math.
"""

from __future__ import annotations

from dataclasses import dataclass

from dartsanalytics.common.enums import DataKind
from dartsanalytics.grip.landmarks import HandFrame
from dartsanalytics.pose.geometry import joint_angle_deg, tilt_from_horizontal_deg

MAX_BARREL_AXIS_CONFIDENCE = 0.6
MIN_BARREL_AXIS_CONFIDENCE = 0.05


@dataclass(frozen=True)
class FeatureValue:
    value: float
    confidence: float
    data_kind: DataKind = DataKind.ESTIMATED

    def to_dict(self) -> dict:
        return {"value": self.value, "confidence": self.confidence, "data_kind": self.data_kind.value}


@dataclass(frozen=True)
class GripFeatures:
    thumb_curl_angle_deg: FeatureValue | None
    index_curl_angle_deg: FeatureValue | None
    middle_curl_angle_deg: FeatureValue | None
    wrist_angle_deg: FeatureValue | None
    barrel_axis_deg: FeatureValue | None  # proxy estimate — see module docstring

    def to_dict(self) -> dict:
        return {
            name: (value.to_dict() if value is not None else None)
            for name, value in (
                ("thumb_curl_angle_deg", self.thumb_curl_angle_deg),
                ("index_curl_angle_deg", self.index_curl_angle_deg),
                ("middle_curl_angle_deg", self.middle_curl_angle_deg),
                ("wrist_angle_deg", self.wrist_angle_deg),
                ("barrel_axis_deg", self.barrel_axis_deg),
            )
        }


def _min_confidence(*confidences: float) -> float:
    return min(confidences)


def _finger_curl_angle(frame: HandFrame, mcp: str, pip: str, tip: str) -> FeatureValue | None:
    a = frame.get(mcp)
    vertex = frame.get(pip)
    c = frame.get(tip)
    if not (a and vertex and c):
        return None
    try:
        angle = joint_angle_deg(a.as_xy(), vertex.as_xy(), c.as_xy())
    except ValueError:
        return None
    return FeatureValue(value=angle, confidence=_min_confidence(a.confidence, vertex.confidence, c.confidence))


def compute_grip_features(frame: HandFrame) -> GripFeatures:
    thumb_curl = _finger_curl_angle(frame, "thumb_mcp", "thumb_ip", "thumb_tip")
    index_curl = _finger_curl_angle(frame, "index_mcp", "index_pip", "index_tip")
    middle_curl = _finger_curl_angle(frame, "middle_mcp", "middle_pip", "middle_tip")

    wrist_angle: FeatureValue | None = None
    wrist_pt = frame.get("wrist")
    middle_mcp_pt = frame.get("middle_mcp")
    if wrist_pt and middle_mcp_pt:
        try:
            # Reused as a generic "angle of the line between two points
            # from horizontal" — the left/right naming in tilt_from_horizontal_deg
            # comes from its Phase 5 shoulder/hip use, not a semantic
            # requirement here.
            angle = tilt_from_horizontal_deg(wrist_pt.as_xy(), middle_mcp_pt.as_xy())
            wrist_angle = FeatureValue(
                value=angle, confidence=_min_confidence(wrist_pt.confidence, middle_mcp_pt.confidence)
            )
        except ValueError:
            wrist_angle = None

    barrel_axis: FeatureValue | None = None
    thumb_tip = frame.get("thumb_tip")
    index_tip = frame.get("index_tip")
    if thumb_tip and index_tip:
        try:
            angle = tilt_from_horizontal_deg(thumb_tip.as_xy(), index_tip.as_xy())
            raw_confidence = _min_confidence(thumb_tip.confidence, index_tip.confidence) * MAX_BARREL_AXIS_CONFIDENCE
            confidence = max(MIN_BARREL_AXIS_CONFIDENCE, min(MAX_BARREL_AXIS_CONFIDENCE, raw_confidence))
            barrel_axis = FeatureValue(value=angle, confidence=confidence)
        except ValueError:
            barrel_axis = None

    return GripFeatures(
        thumb_curl_angle_deg=thumb_curl,
        index_curl_angle_deg=index_curl,
        middle_curl_angle_deg=middle_curl,
        wrist_angle_deg=wrist_angle,
        barrel_axis_deg=barrel_axis,
    )
