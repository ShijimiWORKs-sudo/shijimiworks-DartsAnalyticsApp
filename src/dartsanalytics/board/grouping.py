"""Grouping statistics over normalized throw coordinates (docs §11).

All inputs are (normalized_x, normalized_y) pairs already relative to the
calibrated board center (see coordinates.py) — this module does no pixel
math and has no image dependency, which is what makes it independently
testable against the fixed fixtures AGENTS.md §4 asks for (all-center,
all-high, all-low, left-right split, one outlier — see
tests/fixtures/board_patterns.py).

"BULL内率" / "BULL周辺集中率" need a radius threshold, and the real
dartboard's single/double-bull rings give an unambiguous value for the
first; "周辺" (vicinity) has no single official definition, so its radius
is a named, overridable constant rather than a pretended-exact figure
(design principle: 解析不能なものを無理に判定しない — don't manufacture false
precision).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# Standard steel-tip dartboard dimensions (mm): double-bull (50) radius
# ~6.35mm, single-bull (25) outer radius ~15.9mm, board (outer double-ring)
# radius ~170mm. Expressed as fractions of the board radius, matching this
# module's normalized coordinate system (radius_px == 1.0).
NORMALIZED_DBULL_RADIUS = 6.35 / 170.0
NORMALIZED_BULL_RADIUS = 15.9 / 170.0
# "BULL周辺" (bull vicinity) has no official ring definition — this default
# is a documented, overridable convention, not a measured constant.
DEFAULT_BULL_VICINITY_RADIUS = 0.15


@dataclass(frozen=True)
class GroupingStats:
    n: int
    group_center_x: float
    group_center_y: float
    std_x: float
    std_y: float
    covariance_xy: float
    mean_center_distance: float
    rms_distance: float
    max_distance: float
    percentile_radii: dict[str, float]  # keys: "p50", "p75", "p90", "p95"
    bull_rate: float
    bull_vicinity_rate: float
    vertical_bias: float  # mean normalized_y; positive = struck above board center
    horizontal_bias: float  # mean normalized_x; positive = struck right of board center

    def to_dict(self) -> dict:
        return {
            "n": self.n,
            "group_center_x": self.group_center_x,
            "group_center_y": self.group_center_y,
            "std_x": self.std_x,
            "std_y": self.std_y,
            "covariance_xy": self.covariance_xy,
            "mean_center_distance": self.mean_center_distance,
            "rms_distance": self.rms_distance,
            "max_distance": self.max_distance,
            "percentile_radii": self.percentile_radii,
            "bull_rate": self.bull_rate,
            "bull_vicinity_rate": self.bull_vicinity_rate,
            "vertical_bias": self.vertical_bias,
            "horizontal_bias": self.horizontal_bias,
        }


def compute_grouping_stats(
    points: list[tuple[float, float]],
    *,
    bull_vicinity_radius: float = DEFAULT_BULL_VICINITY_RADIUS,
) -> GroupingStats:
    """`points` are (normalized_x, normalized_y) pairs, board-center-relative."""
    if not points:
        raise ValueError("compute_grouping_stats requires at least one point")

    arr = np.array(points, dtype=np.float64)
    xs, ys = arr[:, 0], arr[:, 1]
    n = len(points)

    group_center_x = float(xs.mean())
    group_center_y = float(ys.mean())
    std_x = float(xs.std(ddof=1)) if n > 1 else 0.0
    std_y = float(ys.std(ddof=1)) if n > 1 else 0.0
    covariance_xy = float(np.cov(xs, ys, ddof=1)[0, 1]) if n > 1 else 0.0

    distances_from_bull = np.hypot(xs, ys)
    distances_from_center = np.hypot(xs - group_center_x, ys - group_center_y)

    mean_center_distance = float(distances_from_center.mean())
    rms_distance = float(math.sqrt(float((distances_from_center**2).mean())))
    max_distance = float(distances_from_center.max())
    percentile_radii = {
        f"p{p}": float(np.percentile(distances_from_center, p)) for p in (50, 75, 90, 95)
    }

    bull_rate = float(np.mean(distances_from_bull <= NORMALIZED_BULL_RADIUS))
    bull_vicinity_rate = float(np.mean(distances_from_bull <= bull_vicinity_radius))

    return GroupingStats(
        n=n,
        group_center_x=group_center_x,
        group_center_y=group_center_y,
        std_x=std_x,
        std_y=std_y,
        covariance_xy=covariance_xy,
        mean_center_distance=mean_center_distance,
        rms_distance=rms_distance,
        max_distance=max_distance,
        percentile_radii=percentile_radii,
        bull_rate=bull_rate,
        bull_vicinity_rate=bull_vicinity_rate,
        vertical_bias=group_center_y,
        horizontal_bias=group_center_x,
    )
