import math

import pytest

from dartsanalytics.board.grouping import (
    DEFAULT_BULL_VICINITY_RADIUS,
    NORMALIZED_BULL_RADIUS,
    compute_grouping_stats,
)
from tests.fixtures.board_patterns import (
    all_center,
    all_high,
    all_low,
    left_right_even_split,
    one_outlier,
)


def test_all_center_has_zero_spread_and_full_bull_rate():
    stats = compute_grouping_stats(all_center())
    assert stats.group_center_x == 0.0
    assert stats.group_center_y == 0.0
    assert stats.std_x == 0.0
    assert stats.std_y == 0.0
    assert stats.mean_center_distance == 0.0
    assert stats.max_distance == 0.0
    assert stats.bull_rate == 1.0
    assert stats.bull_vicinity_rate == 1.0
    assert stats.vertical_bias == 0.0
    assert stats.horizontal_bias == 0.0


def test_all_high_has_positive_vertical_bias_only():
    stats = compute_grouping_stats(all_high())
    assert stats.vertical_bias == pytest.approx(0.3)
    assert stats.horizontal_bias == pytest.approx(0.0)
    assert stats.bull_rate == 0.0  # 0.3 is well outside NORMALIZED_BULL_RADIUS


def test_all_low_has_negative_vertical_bias_only():
    stats = compute_grouping_stats(all_low())
    assert stats.vertical_bias == pytest.approx(-0.3)
    assert stats.horizontal_bias == pytest.approx(0.0)


def test_high_and_low_are_mirror_images():
    high = compute_grouping_stats(all_high())
    low = compute_grouping_stats(all_low())
    assert high.vertical_bias == pytest.approx(-low.vertical_bias)
    assert high.mean_center_distance == pytest.approx(low.mean_center_distance)


def test_left_right_even_split_has_zero_net_bias_but_large_spread():
    stats = compute_grouping_stats(left_right_even_split())
    assert stats.horizontal_bias == pytest.approx(0.0)
    assert stats.vertical_bias == pytest.approx(0.0)
    assert stats.std_x > 0.0  # spread exists even though the mean is centered
    assert stats.std_y == 0.0


def test_one_outlier_dominates_max_distance_but_not_group_center():
    tight_only_center_x = sum(p[0] for p in one_outlier()[:23]) / 23
    stats = compute_grouping_stats(one_outlier())
    # The single outlier pulls the group center only slightly...
    assert abs(stats.group_center_x - tight_only_center_x) < 0.1
    # ...but dominates the max distance and the top percentile radius.
    assert stats.max_distance > stats.percentile_radii["p90"]
    assert stats.percentile_radii["p95"] < stats.max_distance


def test_percentile_radii_are_nondecreasing():
    stats = compute_grouping_stats(one_outlier())
    p = stats.percentile_radii
    assert p["p50"] <= p["p75"] <= p["p90"] <= p["p95"]


def test_rms_distance_greater_or_equal_mean_distance():
    """RMS >= arithmetic mean always holds (power-mean inequality) — a good
    sanity check that catches a swapped formula."""
    for builder in (all_high, left_right_even_split, one_outlier):
        stats = compute_grouping_stats(builder())
        assert stats.rms_distance >= stats.mean_center_distance - 1e-9


def test_compute_grouping_stats_rejects_empty_input():
    with pytest.raises(ValueError):
        compute_grouping_stats([])


def test_single_point_has_zero_std_and_defined_stats():
    stats = compute_grouping_stats([(0.1, 0.2)])
    assert stats.n == 1
    assert stats.std_x == 0.0
    assert stats.mean_center_distance == 0.0  # the single point IS the group center


def test_bull_radius_constants_are_sane_fractions_of_board_radius():
    assert 0 < NORMALIZED_BULL_RADIUS < DEFAULT_BULL_VICINITY_RADIUS < 1.0


def test_bull_rate_matches_manual_count():
    points = [(0.0, 0.0)] * 5 + [(0.5, 0.5)] * 5  # 5 in bull, 5 far outside
    stats = compute_grouping_stats(points)
    assert stats.bull_rate == pytest.approx(0.5)
