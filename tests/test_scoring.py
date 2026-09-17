import pytest

from dartsanalytics.common.enums import Ring
from dartsanalytics.countup.scoring import format_segment, score_for


@pytest.mark.parametrize(
    "ring,number,expected_score,expected_segment",
    [
        (Ring.SINGLE, 20, 20, "S20"),
        (Ring.DOUBLE, 20, 40, "D20"),
        (Ring.TRIPLE, 20, 60, "T20"),
        (Ring.SINGLE, 1, 1, "S1"),
        (Ring.TRIPLE, 19, 57, "T19"),
        (Ring.BULL, None, 25, "BULL"),
        (Ring.DBULL, None, 50, "DBULL"),
        (Ring.MISS, None, 0, "MISS"),
    ],
)
def test_score_for_and_format_segment(ring, number, expected_score, expected_segment):
    assert score_for(ring, number) == expected_score
    assert format_segment(ring, number) == expected_segment


def test_score_for_rejects_out_of_range_number():
    with pytest.raises(ValueError):
        score_for(Ring.SINGLE, 21)
    with pytest.raises(ValueError):
        score_for(Ring.TRIPLE, 0)


def test_score_for_requires_number_for_numbered_rings():
    with pytest.raises(ValueError):
        score_for(Ring.SINGLE, None)
