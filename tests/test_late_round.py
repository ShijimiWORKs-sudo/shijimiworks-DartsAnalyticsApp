import pytest

from dartsanalytics.common.enums import DataKind, DetectionSource, GameType, Ring
from dartsanalytics.integrated.late_round import compare_early_vs_late_rounds
from dartsanalytics.models.entities import PracticeSession, Throw


def _throw(n, *, score, x=None, y=None) -> Throw:
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


def _session(throws: list[Throw]) -> PracticeSession:
    return PracticeSession(account_id="a", player_id="p", game_type=GameType.COUNT_UP, throws=throws)


def test_single_round_session_is_insufficient_data():
    session = _session([_throw(1, score=20), _throw(2, score=20), _throw(3, score=20)])
    result = compare_early_vs_late_rounds(session)
    assert result.insufficient_data is True
    assert result.early_score_average is None
    assert result.late_score_average is None


def test_empty_session_is_insufficient_data():
    session = _session([])
    result = compare_early_vs_late_rounds(session)
    assert result.insufficient_data is True


def test_splits_full_8_round_session_4_and_4():
    # rounds 1-4: score 20/throw; rounds 5-8: score 5/throw (a clear "late
    # round degradation" shape for the test).
    throws = []
    for n in range(1, 25):
        round_number = (n - 1) // 3 + 1
        score = 20 if round_number <= 4 else 5
        throws.append(_throw(n, score=score))
    session = _session(throws)

    result = compare_early_vs_late_rounds(session)
    assert result.insufficient_data is False
    assert result.early_rounds == [1, 2, 3, 4]
    assert result.late_rounds == [5, 6, 7, 8]
    assert result.early_score_average == pytest.approx(20.0)
    assert result.late_score_average == pytest.approx(5.0)
    assert result.score_delta == pytest.approx(-15.0)


def test_odd_round_count_gives_early_half_the_extra_round():
    throws = [_throw(n, score=10) for n in range(1, 16)]  # 5 rounds (15 throws)
    session = _session(throws)
    result = compare_early_vs_late_rounds(session)
    assert result.early_rounds == [1, 2, 3]
    assert result.late_rounds == [4, 5]


def test_dispersion_is_none_when_no_coordinates_present():
    throws = [_throw(n, score=10) for n in range(1, 25)]  # no x/y set anywhere
    session = _session(throws)
    result = compare_early_vs_late_rounds(session)
    assert result.early_dispersion is None
    assert result.late_dispersion is None


def test_dispersion_computed_when_coordinates_present():
    throws = []
    for n in range(1, 25):
        round_number = (n - 1) // 3 + 1
        x, y = (0.0, 0.3) if round_number <= 4 else (0.0, -0.3)
        throws.append(_throw(n, score=10, x=x, y=y))
    session = _session(throws)
    result = compare_early_vs_late_rounds(session)
    assert result.early_dispersion is not None
    assert result.late_dispersion is not None
    assert result.early_dispersion.vertical_bias == pytest.approx(0.3)
    assert result.late_dispersion.vertical_bias == pytest.approx(-0.3)


def test_to_dict_is_json_serializable():
    import json

    throws = [_throw(n, score=10) for n in range(1, 25)]
    session = _session(throws)
    result = compare_early_vs_late_rounds(session)
    json.dumps(result.to_dict(), ensure_ascii=False)
