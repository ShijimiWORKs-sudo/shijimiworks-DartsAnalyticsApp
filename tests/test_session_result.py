from dartsanalytics.common.enums import Ring, SessionStatus
from dartsanalytics.countup.session_result import summarize
from tests.fixtures.countup_patterns import (
    all_dbull_session,
    all_miss_session,
    missing_throws_session,
    one_outlier_session,
)


def test_all_miss_session_totals_zero():
    result = summarize(all_miss_session())
    assert result.total_score == 0
    assert result.throw_average == 0
    assert result.ring_counts[Ring.MISS.value] == 24
    assert sum(result.ring_counts.values()) == 24
    assert result.status == SessionStatus.COMPLETE


def test_all_dbull_session_totals_max():
    result = summarize(all_dbull_session())
    assert result.total_score == 24 * 50
    assert result.throw_average == 50
    assert result.ring_counts[Ring.DBULL.value] == 24
    assert all(rs == 3 * 50 for rs in result.round_scores)  # 3 darts/round


def test_missing_throws_session_is_incomplete_and_partial():
    session = missing_throws_session(num_throws=17)
    result = summarize(session)
    assert result.status == SessionStatus.INCOMPLETE
    assert result.throw_count == 17
    assert result.total_score == 17 * 5  # each throw is S5 = 5 points
    # 17 throws = 5 full rounds (15) + 2 in round 6
    assert len(result.round_scores) == 6


def test_one_outlier_session_dominates_total():
    result = summarize(one_outlier_session())
    # 23 * S1 (=1 each) + 1 * DBULL (=50)
    assert result.total_score == 23 * 1 + 50
    assert result.ring_counts[Ring.DBULL.value] == 1
    assert result.ring_counts[Ring.SINGLE.value] == 23


def test_summary_round_scores_sum_to_total():
    result = summarize(all_dbull_session())
    assert sum(result.round_scores) == result.total_score


def test_summary_ring_counts_sum_to_throw_count():
    for builder in (all_miss_session, all_dbull_session, one_outlier_session):
        result = summarize(builder())
        assert sum(result.ring_counts.values()) == result.throw_count
