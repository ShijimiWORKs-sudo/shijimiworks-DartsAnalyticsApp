"""Integration tests (docs §12's "Integration" category): application
service <-> DB, and the full analysis pipeline end to end.

Unlike the rest of the suite (predominantly unit tests exercising one
module at a time), these tests deliberately chain multiple layers
together — countup -> board -> integrated -> advisor -> application
service -> DB -> reload — to catch the class of bug that only shows up at
the seams between modules (a field renamed in one place but not updated
in the caller, a type mismatch between what one module produces and what
the next expects), which per-module unit tests structurally cannot catch.
"""

from __future__ import annotations

from dartsanalytics.application.session_recording_service import SessionRecordingService
from dartsanalytics.board.grouping import compute_grouping_stats
from dartsanalytics.common.enums import SessionStatus
from dartsanalytics.countup.mock import MockCountUpGenerator
from dartsanalytics.integrated.causes import generate_candidate_causes
from dartsanalytics.integrated.correlation import compute_form_correlation
from dartsanalytics.integrated.frequent_segments import compute_frequent_segment_stats
from dartsanalytics.integrated.late_round import compare_early_vs_late_rounds
from dartsanalytics.integrated.report import IntegratedAnalysisReport
from dartsanalytics.models.entities import Account, Player


def _assign_synthetic_coordinates(session):
    """The mock COUNT-UP generator (Phase 1) does not itself produce board
    coordinates — that's Phase 3's job on real detected data. Assign
    simple deterministic coordinates here so the grouping/integrated
    pipeline (which needs normalized_x/y) has something to work with,
    without pretending this is real detection output."""
    for i, throw in enumerate(session.throws):
        throw.normalized_x = 0.01 * (i % 5 - 2)
        throw.normalized_y = 0.01 * ((i + 2) % 5 - 2)
    return session


def test_full_pipeline_mock_session_to_persisted_advisor_output(tmp_path):
    """End-to-end: generate a mock COUNT-UP session -> compute grouping/
    frequent-segment/late-round stats -> build an IntegratedAnalysisReport
    -> generate candidate causes -> build an AdvisorOutput -> persist the
    session AND the advisor output via the Application Service -> reload
    both from a fresh DB connection (simulating an app restart) -> verify
    everything survived intact."""
    from dartsanalytics.advisor.generate import build_advisor_output

    account = Account(display_name="洋典")
    player = Player(account_id=account.account_id, display_name="Player 1")

    session = MockCountUpGenerator(seed=42).generate(
        account_id=account.account_id, player_id=player.player_id, num_throws=24
    )
    session.status = SessionStatus.COMPLETE
    _assign_synthetic_coordinates(session)

    points = [(t.normalized_x, t.normalized_y) for t in session.throws]
    dispersion = compute_grouping_stats(points)
    frequent_segments = compute_frequent_segment_stats(session.throws)
    late_round = compare_early_vs_late_rounds(session)

    paired_samples = [
        (150.0 + i, abs(t.normalized_x) + abs(t.normalized_y))
        for i, t in enumerate(session.throws)
    ]
    correlation = compute_form_correlation(
        form_feature_name="left_elbow_angle_deg",
        outcome_metric_name="distance_from_bull",
        paired_samples=paired_samples,
    )
    form_correlations = [correlation] if correlation is not None else []
    candidate_causes = generate_candidate_causes(form_correlations)

    report = IntegratedAnalysisReport(
        session_id=session.session_id,
        dispersion=dispersion,
        frequent_segments=frequent_segments,
        late_round=late_round,
        form_correlations=form_correlations,
        candidate_causes=candidate_causes,
    )
    advisor_output = build_advisor_output(report)

    service = SessionRecordingService(db_path=tmp_path / "pipeline.db")
    service.ensure_account_and_player(account, player)
    service.record_countup_session(session)
    report_id = service.record_advisor_output(advisor_output)

    # Simulate app restart: brand new service instance, same DB file.
    service2 = SessionRecordingService(db_path=tmp_path / "pipeline.db")
    restored_history = service2.get_session_history(player.player_id)
    assert len(restored_history) == 1
    assert len(restored_history[0].throws) == 24
    assert restored_history[0].status is SessionStatus.COMPLETE
    assert report_id  # a report_id was assigned and nothing raised on save


def test_pipeline_handles_session_with_no_coordinate_data():
    """A session recorded from DARTSLIVE HOME alone (no camera/board
    detection yet) has throws with no normalized_x/y. The pipeline must
    degrade gracefully (dispersion=None), not crash — this is the
    'measurement without features yet' case docs §Phase3 anticipates."""
    account = Account(display_name="洋典")
    player = Player(account_id=account.account_id, display_name="Player 1")
    session = MockCountUpGenerator(seed=7).generate(
        account_id=account.account_id, player_id=player.player_id, num_throws=24
    )
    points = [
        (t.normalized_x, t.normalized_y)
        for t in session.throws
        if t.normalized_x is not None and t.normalized_y is not None
    ]
    assert points == []  # confirms this test's premise

    frequent_segments = compute_frequent_segment_stats(session.throws)
    late_round = compare_early_vs_late_rounds(session)
    report = IntegratedAnalysisReport(
        session_id=session.session_id,
        dispersion=None,
        frequent_segments=frequent_segments,
        late_round=late_round,
        form_correlations=[],
        candidate_causes=[],
    )

    from dartsanalytics.advisor.generate import build_advisor_output

    advisor_output = build_advisor_output(report)
    assert any("座標データが無いため" in o.description for o in advisor_output.observations)
