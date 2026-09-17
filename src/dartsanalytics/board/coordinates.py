"""Pixel -> normalized board coordinate conversion (docs §10).

Coordinate convention (documented explicitly since it is not visually
obvious from code): normalized_x is positive to the right, normalized_y is
positive UPWARD (image pixel y, which grows downward, is flipped here so
that "上下偏り" / up-down bias in dartsanalytics.board.grouping has an
intuitive sign: positive normalized_y = struck above center).

The board center from calibration is treated as coincident with the bull
center — true for a properly mounted/photographed board and good enough
for Phase 3's scope; nothing here attempts a separate bull-specific
calibration.

angle_deg follows standard math convention: 0° = right (+x), 90° = up
(+y), counterclockwise. It is NOT yet aligned to dartboard segment
boundaries (that alignment is a natural Phase 4+/UI extension once
segment-detection is needed, not required for Phase 3's grouping stats).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dartsanalytics.board.calibration import BoardCalibration


@dataclass(frozen=True)
class NormalizedPoint:
    raw_x: float
    raw_y: float
    normalized_x: float
    normalized_y: float
    distance_from_bull: float
    angle_deg: float

    def to_dict(self) -> dict:
        return {
            "raw_x": self.raw_x,
            "raw_y": self.raw_y,
            "normalized_x": self.normalized_x,
            "normalized_y": self.normalized_y,
            "distance_from_bull": self.distance_from_bull,
            "angle": self.angle_deg,
        }


def normalize_point(raw_x_px: float, raw_y_px: float, calibration: BoardCalibration) -> NormalizedPoint:
    if calibration.radius_px <= 0:
        raise ValueError(f"calibration.radius_px must be > 0, got {calibration.radius_px!r}")

    normalized_x = (raw_x_px - calibration.center_x_px) / calibration.radius_px
    normalized_y = (calibration.center_y_px - raw_y_px) / calibration.radius_px  # flip: image y grows down
    distance_from_bull = math.hypot(normalized_x, normalized_y)
    angle_deg = math.degrees(math.atan2(normalized_y, normalized_x))

    return NormalizedPoint(
        raw_x=raw_x_px,
        raw_y=raw_y_px,
        normalized_x=normalized_x,
        normalized_y=normalized_y,
        distance_from_bull=distance_from_bull,
        angle_deg=angle_deg,
    )
