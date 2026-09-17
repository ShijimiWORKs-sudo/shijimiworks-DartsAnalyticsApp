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


def bull_heavy_with_outliers() -> list[tuple[float, float]]:
    """20 throws dead-center (well inside the BULL ring) + 4 wide-scatter
    outliers. Built for docs §5's "単に「ブル率が高い＝まとまっている」と
    判定しない" (don't judge "high BULL rate" as "well grouped") — bull_rate
    is high (20/24 ≈ 0.83) while max_distance/rms_distance/percentile
    radii are all large because of the 4 outliers, proving the two metric
    families move independently."""
    center = [(0.0, 0.0)] * 20
    outliers = [(0.6, 0.6), (-0.6, 0.6), (0.6, -0.6), (-0.6, -0.6)]
    return center + outliers


def tight_but_off_target() -> list[tuple[float, float]]:
    """24 throws tightly clustered together, but the whole cluster sits far
    from BULL. The mirror image of bull_heavy_with_outliers: proves tight
    grouping-quality numbers do NOT imply a high bull_rate."""
    return [(0.4 + 0.005 * (i % 3 - 1), 0.4 + 0.005 * ((i + 1) % 3 - 1)) for i in range(24)]
