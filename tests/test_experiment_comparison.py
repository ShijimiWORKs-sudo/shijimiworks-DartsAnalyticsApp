import pytest

from dartsanalytics.common.enums import DataKind, DetectionSource, GameType, Ring
from dartsanalytics.experiments.comparison import compare_baseline_vs_test
from dartsanalytics.models.entities import PracticeSession, Throw


def _throw(n, *, score=20, x=0.0, y=0.0) -> Throw:
    round_number = (n - 1) // 3 + 1
    return Throw(
        session_id="s1",
        round_id=f"r{round_number}",
        round_number=round_number,
        dart_index=(n - 1) % 3 + 1,
        throw_number_in_session=n,
        detection_source=DetectionSource.MOCK,
        data_kind=DataKind.MEASURED,
        score=score,
        ring=Ring.SINGLE,
        normalized_x=x,
        normalized_y=y,
    )


def _session(throws, session_id="s1") -> PracticeSession:
    s = PracticeSession(account_id="a", player_id="p", game_type=GameType.COUNT_UP, throws=throws)
    s.session_id = session_id
    for t in throws:
        t.session_id = session_id
    return s


def _pooled_session(n_throws, *, score, x, y, id_prefix="s"):
    """Split n_throws across as many 24-throw sessions as needed (throw_number_in_session must be 1..24)."""
    sessions = []
    remaining = n_throws
    idx = 0
    while remaining > 0:
        take = min(24, remaining)
        throws = [_throw(i + 1, score=score, x=x, y=y) for i in range(take)]
        sessions.append(_session(throws, session_id=f"{id_prefix}{idx}"))
        remaining -= take
        idx += 1
    return sessions


def test_rejects_empty_groups():
    baseline = _pooled_session(30, score=10, x=0.0, y=0.0)
    with pytest.raises(ValueError):
        compare_baseline_vs_test([], baseline)
    with pytest.raises(ValueError):
        compare_baseline_vs_test(baseline, [])


def test_identical_groups_have_zero_deltas():
    baseline = _pooled_session(30, score=15, x=0.1, y=0.1, id_prefix="b")
    test = _pooled_session(30, score=15, x=0.1, y=0.1, id_prefix="t")
    result = compare_baseline_vs_test(baseline, test)
    for m in result.metrics:
        if m.delta is not None:
            assert m.delta == pytest.approx(0.0, abs=1e-9)


def test_throw_counts_are_pooled_across_sessions():
    baseline = _pooled_session(48, score=10, x=0.0, y=0.0, id_prefix="b")  # 2 sessions of 24
    test = _pooled_session(30, score=10, x=0.0, y=0.0, id_prefix="t")
    result = compare_baseline_vs_test(baseline, test)
    assert result.baseline_throw_count == 48
    assert result.test_throw_count == 30


def test_countup_average_reflects_score_change():
    baseline = _pooled_session(30, score=10, x=0.0, y=0.0, id_prefix="b")
    test = _pooled_session(30, score=20, x=0.0, y=0.0, id_prefix="t")
    result = compare_baseline_vs_test(baseline, test)
    countup = next(m for m in result.metrics if m.metric_name == "countup_average")
    assert countup.baseline_value == pytest.approx(10.0)
    assert countup.test_value == pytest.approx(20.0)
    assert countup.delta == pytest.approx(10.0)


def test_dispersion_metrics_none_when_no_coordinates():
    baseline_throws = [
        Throw(
            session_id="b0",
            round_id="r1",
            round_number=1,
            dart_index=(i % 3) + 1,
            throw_number_in_session=i + 1,
            detection_source=DetectionSource.MOCK,
            data_kind=DataKind.MEASURED,
            score=10,
            ring=Ring.SINGLE,
        )
        for i in range(3)
    ]
    baseline = [_session(baseline_throws, "b0")]
    test = _pooled_session(3, score=10, x=0.0, y=0.0, id_prefix="t")
    result = compare_baseline_vs_test(baseline, test)
    bull_rate = next(m for m in result.metrics if m.metric_name == "bull_rate")
    assert bull_rate.baseline_value is None
    assert bull_rate.delta is None


def test_to_dict_is_json_serializable():
    import json

    baseline = _pooled_session(30, score=10, x=0.0, y=0.0, id_prefix="b")
    test = _pooled_session(30, score=15, x=0.05, y=0.05, id_prefix="t")
    result = compare_baseline_vs_test(baseline, test)
    json.dumps(result.to_dict(), ensure_ascii=False)
