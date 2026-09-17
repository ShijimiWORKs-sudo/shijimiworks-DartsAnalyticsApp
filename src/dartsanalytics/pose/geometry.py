"""Pure-math geometry helpers for pose features — no ML, no image I/O.

Kept separate from landmarker.py so the actual angle math is testable with
synthetic coordinates (no model, no image) — this is the part of Phase 5
that can be rigorously verified in this environment; see
docs/codex/reports/phase5_notes.md for what still needs real footage.

Coordinate convention matches dartsanalytics.board.coordinates: y is
flipped so "up" is positive, for the same reason (intuitive sign on
tilt/lean features). MediaPipe landmarks come in image-pixel convention
(y grows downward); callers pass raw (x, y) and this module flips
internally where "up" matters.
"""

from __future__ import annotations

import math

Point = tuple[float, float]


def midpoint(a: Point, b: Point) -> Point:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def joint_angle_deg(a: Point, vertex: Point, c: Point) -> float:
    """Interior angle at `vertex`, between rays vertex->a and vertex->c.

    E.g. for an elbow angle: a=shoulder, vertex=elbow, c=wrist. A fully
    extended arm is ~180°; a fully bent one approaches 0°.
    """
    v1 = (a[0] - vertex[0], a[1] - vertex[1])
    v2 = (c[0] - vertex[0], c[1] - vertex[1])
    mag1, mag2 = math.hypot(*v1), math.hypot(*v2)
    if mag1 == 0 or mag2 == 0:
        raise ValueError("degenerate input: vertex coincides with a or c")
    cos_theta = (v1[0] * v2[0] + v1[1] * v2[1]) / (mag1 * mag2)
    cos_theta = max(-1.0, min(1.0, cos_theta))  # guard float drift outside [-1, 1]
    return math.degrees(math.acos(cos_theta))


def tilt_from_vertical_deg(bottom: Point, top: Point) -> float:
    """Angle of the bottom->top line from vertical (image pixel coords, y
    grows downward). 0° = top is directly above bottom (perfectly upright).
    Positive = leaning toward +x (right in image coords).
    """
    dx = top[0] - bottom[0]
    dy = bottom[1] - top[1]  # flip: "up" positive
    if dx == 0 and dy == 0:
        raise ValueError("degenerate input: bottom coincides with top")
    return math.degrees(math.atan2(dx, dy))


def tilt_from_horizontal_deg(left: Point, right: Point) -> float:
    """Angle of the left->right line from horizontal (image pixel coords).
    0° = perfectly level. Positive = right point higher than left (image y
    flipped so 'higher' is intuitive).
    """
    dx = right[0] - left[0]
    dy = left[1] - right[1]  # flip: "up" positive
    if dx == 0 and dy == 0:
        raise ValueError("degenerate input: left coincides with right")
    return math.degrees(math.atan2(dy, dx))
