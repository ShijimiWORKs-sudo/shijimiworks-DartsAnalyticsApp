import pytest

from dartsanalytics.common.enums import DataKind, DetectionSource, GameType, Ring
from dartsanalytics.integrated.correlation import FormCorrelation
from dartsanalytics.integrated.report import build_integrated_report
from dartsanalytics.models.entities import PracticeSession, Throw


def _throw(n, *, score=20, x=None, y=None) -> Throw:
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
        segment="20",
        actual_target="20",
        normalized_x=x,
        normalized_y=y,
    )


def _session(throws: list[Throw]) -> PracticeSession:
    return PracticeSession(account_id="a", player_id="p", game_type=GameType.COUNT_UP, throws=throws)


def test_rejects_session_with_no_throws():
    with pytest.raises(ValueError):
        build_integrated_report(_session([]))


def test_report_without_coordinates_has_no_dispersion():
    session = _session([_throw(n) for n in range(1, 25)])
    report = build_integrated_report(session)
    assert report.dispersion is None
    assert report.frequent_segments is not None
    assert report.frequent_segments.n == 24
    assert report.late_round.insufficient_data is False


def test_report_with_coordinates_has_dispersion():
    throws = [_throw(n, x=0.1, y=0.1) for n in range(1, 25)]
    session = _session(throws)
    report = build_integrated_report(session)
    assert report.dispersion is not None
    assert report.dispersion.n == 24


def test_report_without_correlations_has_no_candidate_causes():
    session = _session([_throw(n) for n in range(1, 25)])
    report = build_integrated_report(session)
    assert report.form_correlations == []
    assert report.candidate_causes == []


def test_report_with_strong_correlation_produces_candidate_cause():
    session = _session([_throw(n) for n in range(1, 25)])
    strong_corr = FormCorrelation(
        form_feature_name="right_elbow_angle_deg",
        outcome_metric_name="vertical_bias",
        n=10,
        pearson_r=0.85,
        confidence=0.6,
    )
    report = build_integrated_report(session, form_correlations=[strong_corr])
    assert len(report.form_correlations) == 1
    assert len(report.candidate_causes) == 1
    assert report.candidate_causes[0].category == "肘/前腕角度"


def test_report_is_json_serializable():
    import json

    throws = [_throw(n, x=0.1, y=0.1) for n in range(1, 25)]
    session = _session(throws)
    report = build_integrated_report(session)
    json.dumps(report.to_dict(), ensure_ascii=False)


def test_report_session_id_matches_input_session():
    session = _session([_throw(n) for n in range(1, 25)])
    report = build_integrated_report(session)
    assert report.session_id == session.session_id
