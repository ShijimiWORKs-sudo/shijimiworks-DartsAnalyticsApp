"""Fixed spatial fixtures for grouping-stats tests (AGENTS.md §4).

These are the fixtures Phase 1 deferred (see tests/fixtures/countup_patterns.py
docstring) because they need real normalized x/y coordinates, which only
exist from Phase 3 onward.
"""

from __future__ import annotations


def all_center() -> list[tuple[float, float]]:
    """All 24 throws land exactly at the board center."""
    return [(0.0, 0.0)] * 24


def all_high() -> list[tuple[float, float]]:
    """All throws above center (positive normalized_y), centered horizontally."""
    return [(0.0, 0.3)] * 24


def all_low() -> list[tuple[float, float]]:
    """All throws below center (negative normalized_y)."""
    return [(0.0, -0.3)] * 24


def left_right_even_split() -> list[tuple[float, float]]:
    """Evenly split between left and right of center, none in the middle."""
    left = [(-0.3, 0.0)] * 12
    right = [(0.3, 0.0)] * 12
    return left + right


def one_outlier() -> list[tuple[float, float]]:
    """23 throws tightly grouped near center, one far outlier."""
    tight = [(0.01 * (i % 3 - 1), 0.01 * ((i + 1) % 3 - 1)) for i in range(23)]
    return tight + [(0.9, 0.9)]
