import pytest

from dartsanalytics.common.enums import DataKind, DetectionSource, Ring
from dartsanalytics.integrated.frequent_segments import (
    compute_frequent_segment_stats,
    find_direction_streaks,
)
from dartsanalytics.models.entities import Throw


def _throw(n, *, ring=Ring.SINGLE, segment="20", x=None, y=None) -> Throw:
    return Throw(
        session_id="s1",
        round_id=f"r{(n - 1) // 3 + 1}",
        round_number=(n - 1) // 3 + 1,
        dart_index=(n - 1) % 3 + 1,
        throw_number_in_session=n,
        detection_source=DetectionSource.MOCK,
        data_kind=DataKind.MEASURED,
        score=20,
        segment=segment,
        ring=ring,
        actual_target=segment,
        normalized_x=x,
        normalized_y=y,
    )


# --- find_direction_streaks -------------------------------------------------


def test_empty_input_has_zero_streak():
    result = find_direction_streaks([], axis="horizontal")
    assert result.max_streak == 0
    assert result.streak_lengths == []


def test_all_same_direction_is_one_long_streak():
    result = find_direction_streaks([0.1, 0.2, 0.15, 0.3], axis="horizontal")
    assert result.max_streak == 4
    assert result.streak_lengths == [4]


def test_alternating_direction_has_no_streaks_over_one():
    result = find_direction_streaks([0.1, -0.1, 0.1, -0.1], axis="horizontal")
    assert result.max_streak == 1
    assert result.streak_lengths == []


def test_zero_breaks_a_streak():
    result = find_direction_streaks([0.1, 0.1, 0.0, 0.1, 0.1, 0.1], axis="vertical")
    assert result.streak_lengths == [2, 3]
    assert result.max_streak == 3


def test_rejects_invalid_axis():
    with pytest.raises(ValueError):
        find_direction_streaks([0.1, 0.2], axis="diagonal")


# --- compute_frequent_segment_stats -----------------------------------------


def test_rejects_empty_throw_list():
    with pytest.raises(ValueError):
        compute_frequent_segment_stats([])


def test_segment_and_ring_counts():
    throws = [
        _throw(1, ring=Ring.SINGLE, segment="20"),
        _throw(2, ring=Ring.SINGLE, segment="20"),
        _throw(3, ring=Ring.TRIPLE, segment="T20"),
        _throw(4, ring=Ring.MISS, segment=None),
    ]
    stats = compute_frequent_segment_stats(throws)
    assert stats.n == 4
    assert stats.segment_counts == {"20": 2, "T20": 1}
    assert stats.ring_counts["SINGLE"] == 2
    assert stats.ring_counts["TRIPLE"] == 1
    assert stats.ring_counts["MISS"] == 1
    assert stats.ring_counts["DOUBLE"] == 0


def test_streaks_computed_from_coordinates_in_throw_order():
    throws = [
        _throw(1, x=0.2, y=0.1),
        _throw(2, x=0.3, y=0.1),
        _throw(3, x=0.1, y=-0.1),
        _throw(4, x=-0.2, y=-0.1),
    ]
    stats = compute_frequent_segment_stats(throws)
    assert stats.horizontal_streaks.max_streak == 3  # three positive-x throws in a row
    assert stats.vertical_streaks.max_streak == 2  # two positive-y then two negative-y


def test_missing_coordinates_are_simply_excluded_not_crashed():
    throws = [_throw(1, x=None, y=None), _throw(2, x=0.1, y=0.1)]
    stats = compute_frequent_segment_stats(throws)
    assert stats.horizontal_streaks.max_streak == 1  # only one coordinate present
