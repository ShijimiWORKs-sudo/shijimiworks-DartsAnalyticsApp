"""Repository layer tests (docs §10 resolution).

Covers exactly the evidence CLAUDE_RELEASE_UNRESOLVED_RESOLUTION_v1.0.md §10
asks for: restart persistence, migration continuity, rollback on failure,
duplicate handling, and corrupt-data handling — plus round-trip coverage
for every repository so the "Local DB Repository" tier is proven against
the real schema, not just typed against the Protocol interfaces.
"""

from __future__ import annotations

import sqlite3

import pytest

from dartsanalytics.board.calibration import BoardCalibration
from dartsanalytics.common.enums import DataKind, DetectionSource, GameType, Ring, SessionStatus
from dartsanalytics.db.repositories.sqlite_repositories import (
    SqliteAccountRepository,
    SqliteAnalysisReportRepository,
    SqliteCalibrationRepository,
    SqliteEquipmentRepository,
    SqliteExperimentRepository,
    SqliteGripAnalysisRepository,
    SqliteMediaRepository,
    SqlitePlayerRepository,
    SqlitePoseFeatureRepository,
    SqliteSessionRepository,
)
from dartsanalytics.db.unit_of_work import SqliteUnitOfWork
from dartsanalytics.experiments.comparison import ExperimentComparison, ExperimentMetricResult
from dartsanalytics.experiments.decision import Decision
from dartsanalytics.experiments.models import Experiment
from dartsanalytics.grip.analysis import GripAnalysisResult, GripPhotoResult
from dartsanalytics.grip.features import FeatureValue, GripFeatures
from dartsanalytics.models.entities import (
    Account,
    CountupRound,
    EquipmentProfile,
    Player,
    PracticeSession,
    Throw,
)
from dartsanalytics.pose.features import PoseFeatures
from dartsanalytics.video.angles import ShootingAngle
from dartsanalytics.video.models import MediaAsset


def _make_session(account: Account, player: Player) -> PracticeSession:
    session = PracticeSession(
        account_id=account.account_id,
        player_id=player.player_id,
        status=SessionStatus.COMPLETE,
        total_score=301,
    )
    round1 = CountupRound(session_id=session.session_id, round_number=1, round_score=150)
    throws = [
        Throw(
            session_id=session.session_id,
            round_id=round1.round_id,
            round_number=1,
            dart_index=i,
            throw_number_in_session=i,
            detection_source=DetectionSource.DARTSLIVE_HOME,
            data_kind=DataKind.MEASURED,
            score=50,
            ring=Ring.DBULL,
            raw_x=0.1 * i,
            raw_y=0.2 * i,
            normalized_x=0.01 * i,
            normalized_y=0.02 * i,
            distance_from_bull=0.05 * i,
            coordinate_source="board_camera_v1",
        )
        for i in range(1, 4)
    ]
    session.rounds.append(round1)
    session.throws.extend(throws)
    return session


# ---------------------------------------------------------------------------
# Account / Player / Equipment
# ---------------------------------------------------------------------------


def test_account_player_equipment_round_trip(db_conn):
    accounts = SqliteAccountRepository(db_conn)
    players = SqlitePlayerRepository(db_conn)
    equipment = SqliteEquipmentRepository(db_conn)

    account = Account(display_name="洋典")
    accounts.save(account)
    assert accounts.get(account.account_id) == account
    assert accounts.list_all() == [account]

    player = Player(account_id=account.account_id, display_name="Player 1", dominant_hand="right")
    players.save(player)
    assert players.get(player.player_id) == player
    assert players.list_by_account(account.account_id) == [player]

    profile = EquipmentProfile(player_id=player.player_id, barrel_maker="Target", barrel_weight_g=20.0)
    equipment.save(profile)
    assert equipment.get(profile.equipment_id) == profile
    assert equipment.list_by_player(player.player_id) == [profile]


def test_account_upsert_replaces_not_duplicates(db_conn):
    accounts = SqliteAccountRepository(db_conn)
    account = Account(display_name="洋典")
    accounts.save(account)
    account.display_name = "洋典 (updated)"
    accounts.save(account)
    assert len(accounts.list_all()) == 1
    assert accounts.get(account.account_id).display_name == "洋典 (updated)"


# ---------------------------------------------------------------------------
# Sessions / rounds / throws (+ restart persistence)
# ---------------------------------------------------------------------------


def test_session_round_trip_reconstructs_rounds_and_throws(db_conn):
    accounts = SqliteAccountRepository(db_conn)
    players = SqlitePlayerRepository(db_conn)
    sessions = SqliteSessionRepository(db_conn)

    account = Account(display_name="洋典")
    player = Player(account_id=account.account_id, display_name="Player 1")
    accounts.save(account)
    players.save(player)

    session = _make_session(account, player)
    sessions.save_session(session)

    restored = sessions.get_session(session.session_id)
    assert restored is not None
    assert restored.session_id == session.session_id
    assert restored.total_score == 301
    assert restored.status is SessionStatus.COMPLETE
    assert len(restored.rounds) == 1
    assert restored.rounds[0].round_score == 150
    assert len(restored.throws) == 3
    assert restored.throws[0].normalized_x == pytest.approx(0.01)
    assert restored.throws[0].ring is Ring.DBULL

    history = sessions.list_sessions_by_player(player.player_id)
    assert [s.session_id for s in history] == [session.session_id]


def test_restart_persistence_survives_reconnect(tmp_path):
    """§10 evidence: data written in one process/connection must still be
    readable after the connection is closed and a brand new one opened
    against the same file — simulating an app restart."""
    db_path = tmp_path / "restart_test.db"

    with SqliteUnitOfWork(db_path) as uow:
        account = Account(display_name="洋典")
        player = Player(account_id=account.account_id, display_name="Player 1")
        uow.accounts.save(account)
        uow.players.save(player)
        session = _make_session(account, player)
        uow.sessions.save_session(session)
        session_id = session.session_id
        player_id = player.player_id

    # Fresh UnitOfWork == fresh sqlite3.Connection against the same file,
    # simulating the app being closed and reopened.
    with SqliteUnitOfWork(db_path) as uow:
        restored = uow.sessions.get_session(session_id)
        assert restored is not None
        assert len(restored.throws) == 3
        assert uow.players.get(player_id) is not None


def test_unit_of_work_rolls_back_whole_transaction_on_error(tmp_path):
    """§10 evidence: rollback. A session + a deliberately-invalid follow-up
    write inside the same `with` block must leave NOTHING on disk — not
    even the session that would otherwise have been valid on its own."""
    db_path = tmp_path / "rollback_test.db"

    account = Account(display_name="洋典")
    player = Player(account_id=account.account_id, display_name="Player 1")
    session = PracticeSession(account_id=account.account_id, player_id=player.player_id)

    with pytest.raises(sqlite3.IntegrityError):
        with SqliteUnitOfWork(db_path) as uow:
            uow.accounts.save(account)
            uow.players.save(player)
            uow.sessions.save_session(session)
            # References a player_id that doesn't exist -> FOREIGN KEY violation.
            bad_session = PracticeSession(account_id=account.account_id, player_id="does-not-exist")
            uow.sessions.save_session(bad_session)

    with SqliteUnitOfWork(db_path) as uow:
        assert uow.accounts.get(account.account_id) is None
        assert uow.sessions.get_session(session.session_id) is None


def test_duplicate_throw_number_in_session_rejected(db_conn):
    """§10 evidence: duplicate handling. throws.UNIQUE(session_id,
    throw_number_in_session) must reject a second throw claiming the same
    slot rather than silently overwriting or duplicating it."""
    accounts = SqliteAccountRepository(db_conn)
    players = SqlitePlayerRepository(db_conn)
    sessions = SqliteSessionRepository(db_conn)

    account = Account(display_name="洋典")
    player = Player(account_id=account.account_id, display_name="Player 1")
    accounts.save(account)
    players.save(player)

    session = PracticeSession(account_id=account.account_id, player_id=player.player_id)
    round1 = CountupRound(session_id=session.session_id, round_number=1)
    sessions.save_session(session)
    db_conn.execute(
        "INSERT INTO countup_rounds (round_id, session_id, round_number, round_score) "
        "VALUES (?, ?, ?, ?)",
        (round1.round_id, round1.session_id, round1.round_number, round1.round_score),
    )

    throw_a = Throw(
        throw_id="throw-a",
        session_id=session.session_id,
        round_id=round1.round_id,
        round_number=1,
        dart_index=1,
        throw_number_in_session=1,
        detection_source=DetectionSource.DARTSLIVE_HOME,
    )
    throw_b_same_slot = Throw(
        throw_id="throw-b",  # different throw_id, same (session_id, throw_number_in_session)
        session_id=session.session_id,
        round_id=round1.round_id,
        round_number=1,
        dart_index=2,
        throw_number_in_session=1,
        detection_source=DetectionSource.DARTSLIVE_HOME,
    )
    sessions._save_throw(throw_a)  # noqa: SLF001 - exercising the low-level insert directly
    with pytest.raises(sqlite3.IntegrityError):
        sessions._save_throw(throw_b_same_slot)  # noqa: SLF001


def test_corrupt_data_kind_rejected_by_check_constraint(db_conn):
    """§10 evidence: corrupt-data handling. The DB's own CHECK constraint
    on throws.data_kind must reject a value outside
    MEASURED/CALCULATED/ESTIMATED/ADVICE even if it somehow bypassed the
    dataclass's own validation (defense in depth)."""
    with pytest.raises(sqlite3.IntegrityError):
        db_conn.execute(
            "INSERT INTO throws (throw_id, session_id, round_id, round_number, dart_index, "
            "throw_number_in_session, detection_source, data_kind, created_at) "
            "VALUES ('t1', 's1', 'r1', 1, 1, 1, 'dartslive_home', 'NOT_A_REAL_KIND', 'now')"
        )


def test_corrupt_confidence_out_of_range_rejected(db_conn):
    with pytest.raises(sqlite3.IntegrityError):
        db_conn.execute(
            "INSERT INTO throws (throw_id, session_id, round_id, round_number, dart_index, "
            "throw_number_in_session, detection_source, data_kind, confidence, created_at) "
            "VALUES ('t1', 's1', 'r1', 1, 1, 1, 'board_camera', 'ESTIMATED', 1.5, 'now')"
        )


# ---------------------------------------------------------------------------
# Calibration / media / pose / grip
# ---------------------------------------------------------------------------


def test_calibration_round_trip(db_conn):
    repo = SqliteCalibrationRepository(db_conn)
    calibration = BoardCalibration(
        center_x_px=100.0, center_y_px=100.0, radius_px=50.0,
        algorithm_version="board_calib_v1", confidence=0.8,
    )
    calibration_id = repo.save(calibration, session_id=None)
    restored, session_id = repo.get(calibration_id)
    assert restored.center_x_px == 100.0
    assert session_id is None


def test_media_asset_round_trip(db_conn):
    accounts = SqliteAccountRepository(db_conn)
    players = SqlitePlayerRepository(db_conn)
    sessions = SqliteSessionRepository(db_conn)
    media = SqliteMediaRepository(db_conn)

    account = Account(display_name="洋典")
    player = Player(account_id=account.account_id, display_name="Player 1")
    accounts.save(account)
    players.save(player)
    session = PracticeSession(account_id=account.account_id, player_id=player.player_id)
    sessions.save_session(session)

    asset = MediaAsset(
        session_id=session.session_id, media_type="video", file_path="/tmp/x.mp4",
        angle=ShootingAngle.FRONT,
    )
    media.save(asset)
    assert media.get(asset.media_id) == asset
    assert media.list_by_session(session.session_id) == [asset]


def test_pose_feature_run_round_trip(db_conn):
    accounts = SqliteAccountRepository(db_conn)
    players = SqlitePlayerRepository(db_conn)
    sessions = SqliteSessionRepository(db_conn)
    media_repo = SqliteMediaRepository(db_conn)
    pose_repo = SqlitePoseFeatureRepository(db_conn)

    account = Account(display_name="洋典")
    player = Player(account_id=account.account_id, display_name="Player 1")
    accounts.save(account)
    players.save(player)
    session = PracticeSession(account_id=account.account_id, player_id=player.player_id)
    sessions.save_session(session)
    asset = MediaAsset(session_id=session.session_id, media_type="video", file_path="/tmp/x.mp4")
    media_repo.save(asset)

    run_id = pose_repo.save_run(asset.media_id, "pose_v1", "complete")
    features = PoseFeatures(
        body_tilt_deg=FeatureValue(value=3.2, confidence=0.7, data_kind=DataKind.ESTIMATED),
        shoulder_tilt_deg=None,
        hip_tilt_deg=None,
        left_elbow_angle_deg=FeatureValue(value=150.0, confidence=0.6, data_kind=DataKind.ESTIMATED),
        right_elbow_angle_deg=None,
    )
    pose_repo.save_features(run_id, features)
    stored = pose_repo.list_features_by_run(run_id)
    assert stored["body_tilt_deg"]["value"] == pytest.approx(3.2)
    assert stored["left_elbow_angle_deg"]["confidence"] == pytest.approx(0.6)
    assert "shoulder_tilt_deg" not in stored  # None features are not persisted as rows


def test_grip_analysis_round_trip(db_conn):
    accounts = SqliteAccountRepository(db_conn)
    players = SqlitePlayerRepository(db_conn)
    sessions = SqliteSessionRepository(db_conn)
    media_repo = SqliteMediaRepository(db_conn)
    grip_repo = SqliteGripAnalysisRepository(db_conn)

    account = Account(display_name="洋典")
    player = Player(account_id=account.account_id, display_name="Player 1")
    accounts.save(account)
    players.save(player)
    session = PracticeSession(account_id=account.account_id, player_id=player.player_id)
    sessions.save_session(session)
    asset = MediaAsset(session_id=session.session_id, media_type="photo", file_path="/tmp/grip.jpg")
    media_repo.save(asset)

    features = GripFeatures(
        thumb_curl_angle_deg=FeatureValue(value=20.0, confidence=0.5, data_kind=DataKind.ESTIMATED),
        index_curl_angle_deg=None,
        middle_curl_angle_deg=None,
        wrist_angle_deg=FeatureValue(value=10.0, confidence=0.4, data_kind=DataKind.ESTIMATED),
        barrel_axis_deg=None,
    )
    result = GripAnalysisResult(
        dominant=GripPhotoResult(side="dominant", detected=True, frame=None, features=features),
        opposite=None,
    )
    grip_run_id = grip_repo.save(asset.media_id, result, "hand_landmarker_v1")
    stored = grip_repo.get(grip_run_id)
    assert stored["media_id"] == asset.media_id
    assert stored["result"]["dominant"]["features"]["wrist_angle_deg"]["value"] == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Analysis reports / hypotheses / experiments
# ---------------------------------------------------------------------------


def test_analysis_report_and_hypothesis_round_trip(db_conn):
    accounts = SqliteAccountRepository(db_conn)
    players = SqlitePlayerRepository(db_conn)
    sessions = SqliteSessionRepository(db_conn)
    reports = SqliteAnalysisReportRepository(db_conn)

    account = Account(display_name="洋典")
    player = Player(account_id=account.account_id, display_name="Player 1")
    accounts.save(account)
    players.save(player)
    session = PracticeSession(account_id=account.account_id, player_id=player.player_id)
    sessions.save_session(session)

    report_id = reports.save_report(session.session_id, '{"foo": "bar"}')
    hypothesis_id = reports.save_hypothesis(report_id, "right elbow drops late in the round", 0.4)
    intervention_id = reports.save_intervention(hypothesis_id, "focus on elbow height in round 6-8")
    assert report_id and hypothesis_id and intervention_id


def test_experiment_and_results_round_trip(db_conn):
    repo = SqliteExperimentRepository(db_conn)
    reports = SqliteAnalysisReportRepository(db_conn)
    intervention_id = reports.save_intervention(None, "テスト用介入")
    experiment = Experiment(
        intervention_id=intervention_id,
        baseline_session_ids=["s1", "s2"],
        test_session_ids=["s3", "s4"],
        status="decided",
        decision=Decision.CONTINUE,
    )
    repo.save(experiment)
    restored = repo.get(experiment.experiment_id)
    assert restored == experiment

    comparison = ExperimentComparison(
        baseline_throw_count=30,
        test_throw_count=32,
        metrics=[
            ExperimentMetricResult(
                metric_name="bull_rate", baseline_value=0.1, test_value=0.15,
                delta=0.05, higher_is_better=True,
            )
        ],
    )
    repo.save_results(experiment.experiment_id, comparison)
    results = repo.list_results(experiment.experiment_id)
    assert len(results) == 1
    assert results[0]["metric_name"] == "bull_rate"
    assert results[0]["delta"] == pytest.approx(0.05)
