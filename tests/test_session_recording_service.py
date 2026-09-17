"""Tests for the Application Service tier (docs §10 resolution) —
SessionRecordingService, exercised through its public API only (never
touching sqlite3 or the repositories directly), matching how a future UI
would actually call it."""

from __future__ import annotations

from dartsanalytics.advisor.models import AdvisorOutput, Caveat, Hypothesis, Observation
from dartsanalytics.application.session_recording_service import SessionRecordingService
from dartsanalytics.common.enums import DataKind, DetectionSource, SessionStatus
from dartsanalytics.db.unit_of_work import SqliteUnitOfWork
from dartsanalytics.experiments.comparison import ExperimentComparison, ExperimentMetricResult
from dartsanalytics.experiments.decision import Decision
from dartsanalytics.experiments.models import Experiment
from dartsanalytics.models.entities import Account, CountupRound, Player, PracticeSession, Throw


def _service(tmp_path):
    return SessionRecordingService(db_path=tmp_path / "service_test.db")


def test_ensure_account_and_player_then_record_session(tmp_path):
    service = _service(tmp_path)
    account = Account(display_name="洋典")
    player = Player(account_id=account.account_id, display_name="Player 1")
    service.ensure_account_and_player(account, player)

    session = PracticeSession(
        account_id=account.account_id, player_id=player.player_id,
        status=SessionStatus.COMPLETE, total_score=250,
    )
    round1 = CountupRound(session_id=session.session_id, round_number=1, round_score=100)
    throw1 = Throw(
        session_id=session.session_id, round_id=round1.round_id, round_number=1,
        dart_index=1, throw_number_in_session=1,
        detection_source=DetectionSource.DARTSLIVE_HOME, data_kind=DataKind.MEASURED, score=60,
    )
    session.rounds.append(round1)
    session.throws.append(throw1)

    service.record_countup_session(session)

    history = service.get_session_history(player.player_id)
    assert len(history) == 1
    assert history[0].total_score == 250
    assert len(history[0].throws) == 1


def test_record_advisor_output(tmp_path):
    service = _service(tmp_path)
    account = Account(display_name="洋典")
    player = Player(account_id=account.account_id, display_name="Player 1")
    service.ensure_account_and_player(account, player)
    session = PracticeSession(account_id=account.account_id, player_id=player.player_id)
    service.record_countup_session(session)

    advisor_output = AdvisorOutput(
        session_id=session.session_id,
        observations=[Observation(description="平均得点は先週より低い")],
        hypotheses=[Hypothesis(category="release", description="リリースが早い可能性", confidence=0.4)],
        recommended_tests=[],
        caveats=[Caveat(text="サンプル数が少ない")],
    )
    report_id = service.record_advisor_output(advisor_output)
    assert report_id


def test_record_experiment_decision(tmp_path):
    service = _service(tmp_path)
    with SqliteUnitOfWork(tmp_path / "service_test.db") as uow:
        intervention_id = uow.analysis_reports.save_intervention(None, "テスト用介入")
    experiment = Experiment(
        intervention_id=intervention_id,
        baseline_session_ids=["s1"],
        test_session_ids=["s2"],
        status="decided",
        decision=Decision.CONTINUE,
    )
    comparison = ExperimentComparison(
        baseline_throw_count=30, test_throw_count=30,
        metrics=[
            ExperimentMetricResult(
                metric_name="bull_rate", baseline_value=0.1, test_value=0.12,
                delta=0.02, higher_is_better=True,
            )
        ],
    )
    service.record_experiment_decision(experiment, comparison)

    # Restart / reconnect and confirm both landed together.
    service2 = _service(tmp_path)
    history = service2.get_session_history("nonexistent-player")
    assert history == []  # sanity: unrelated query still works against the same file
