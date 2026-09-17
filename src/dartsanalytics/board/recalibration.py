"""Recalibration-prompt logic (docs §7: "キャリブレーション結果を保存し、
精度低下時には再キャリブレーションを促す").

The "保存" half is handled by the §10 repository layer
(dartsanalytics.db.repositories.sqlite_repositories.SqliteCalibrationRepository
— every calibration is persisted with its own confidence and timestamp).
This module is the "精度低下時には促す" half: given a newly computed
BoardCalibration and (optionally) the last known-good one for the same
camera setup, decide whether the user should be asked to recalibrate.

Two independent triggers, either one is sufficient:

  1. **confidence trigger** — this frame's own detection confidence is
     low in absolute terms (below `confidence_floor`), or has dropped
     sharply versus the last known-good calibration
     (`confidence_drop_threshold`). This catches "the board detector
     itself is less sure this time" (worse lighting, partial occlusion,
     etc.) without needing a second calibration to compare against.
  2. **drift trigger** — the newly detected center/radius differs from
     the last known-good one by more than a normalized tolerance. This
     catches "the camera or board physically moved" even when the new
     frame's own confidence looks fine (a confidently-wrong calibration
     is exactly the dangerous case a confidence-only check would miss).

None of the four threshold constants below is a measured, calibrated
value — each is a documented, overridable convention, the same posture as
board.grouping.DEFAULT_BULL_VICINITY_RADIUS (design principle:
解析不能なものを無理に判定しない — don't manufacture false precision by
pretending these thresholds come from measurement).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from dartsanalytics.board.calibration import BoardCalibration

DEFAULT_CONFIDENCE_FLOOR = 0.5  # below common.confidence's REFERENCE bucket
DEFAULT_CONFIDENCE_DROP_THRESHOLD = 0.2  # vs. the previous known-good calibration
DEFAULT_CENTER_DRIFT_THRESHOLD = 0.05  # fraction of the previous radius
DEFAULT_RADIUS_DRIFT_THRESHOLD = 0.10  # fraction of the previous radius


@dataclass(frozen=True)
class RecalibrationAssessment:
    recalibration_recommended: bool
    reasons: list[str] = field(default_factory=list)
    confidence_drop: float | None = None
    center_drift_normalized: float | None = None
    radius_drift_ratio: float | None = None

    def to_dict(self) -> dict:
        return {
            "recalibration_recommended": self.recalibration_recommended,
            "reasons": list(self.reasons),
            "confidence_drop": self.confidence_drop,
            "center_drift_normalized": self.center_drift_normalized,
            "radius_drift_ratio": self.radius_drift_ratio,
        }


def assess_recalibration_need(
    current: BoardCalibration,
    previous: BoardCalibration | None = None,
    *,
    confidence_floor: float = DEFAULT_CONFIDENCE_FLOOR,
    confidence_drop_threshold: float = DEFAULT_CONFIDENCE_DROP_THRESHOLD,
    center_drift_threshold: float = DEFAULT_CENTER_DRIFT_THRESHOLD,
    radius_drift_threshold: float = DEFAULT_RADIUS_DRIFT_THRESHOLD,
) -> RecalibrationAssessment:
    reasons: list[str] = []

    if current.confidence < confidence_floor:
        reasons.append(
            f"current confidence {current.confidence:.2f} is below the floor "
            f"{confidence_floor:.2f}"
        )

    confidence_drop: float | None = None
    center_drift_normalized: float | None = None
    radius_drift_ratio: float | None = None

    if previous is not None and previous.radius_px > 0:
        confidence_drop = previous.confidence - current.confidence
        if confidence_drop > confidence_drop_threshold:
            reasons.append(
                f"confidence dropped by {confidence_drop:.2f} versus the last known-good "
                f"calibration (threshold {confidence_drop_threshold:.2f})"
            )

        center_distance_px = math.hypot(
            current.center_x_px - previous.center_x_px,
            current.center_y_px - previous.center_y_px,
        )
        center_drift_normalized = center_distance_px / previous.radius_px
        if center_drift_normalized > center_drift_threshold:
            reasons.append(
                f"detected center drifted {center_drift_normalized:.2%} of the previous "
                f"radius (threshold {center_drift_threshold:.0%}) — camera or board may "
                "have moved"
            )

        radius_drift_ratio = abs(current.radius_px - previous.radius_px) / previous.radius_px
        if radius_drift_ratio > radius_drift_threshold:
            reasons.append(
                f"detected radius changed by {radius_drift_ratio:.2%} versus the previous "
                f"calibration (threshold {radius_drift_threshold:.0%}) — camera distance/zoom "
                "may have changed"
            )

    return RecalibrationAssessment(
        recalibration_recommended=bool(reasons),
        reasons=reasons,
        confidence_drop=confidence_drop,
        center_drift_normalized=center_drift_normalized,
        radius_drift_ratio=radius_drift_ratio,
    )
