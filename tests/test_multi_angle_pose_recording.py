"""Tests for SessionRecordingService.record_pose_features /
record_multi_angle_pose_analysis (release-readiness.md 未解決事項9:
「multi_angle.pyのセッション全体オーケストレーションへの結線」).

Exercises the Application Service tier only (matches
test_session_recording_service.py's own convention — never touches
sqlite3/the repositories directly).
"""

from __future__ import annotations

import json

import pytest

from dartsanalytics.application.session_recording_service import (
    MultiAngleRecordingResult,
    SessionRecordingService,
)
from dartsanalytics.common.enums import DataKind
from dartsanalytics.db.unit_of_work import SqliteUnitOfWork
from dartsanalytics.models.entities import Account, Player, PracticeSession
from dartsanalytics.pose.features import FeatureValue, PoseFeatures
from dartsanalytics.video.angles import ShootingAngle
from dartsanalytics.video.models import MediaAsset


def _service(tmp_path):
    return SessionRecordingService(db_path=tmp_path / "multi_angle_test.db")


def _setup_account_session(service):
    account = Account(display_name="洋典")
    player = Player(account_id=account.account_id, display_name="Player 1")
    service.ensure_account_and_player(account, player)
    session = PracticeSession(account_id=account.account_id, player_id=player.player_id)
    service.record_countup_session(session)
    return session


def _media_asset(session_id: str, angle: ShootingAngle) -> MediaAsset:
    return MediaAsset(
        session_id=session_id, media_type="video", file_path=f"/tmp/{angle.value}.mp4", angle=angle
    )


def _features(*, body_tilt: float, confidence: float) -> PoseFeatures:
    return PoseFeatures(
        body_tilt_deg=FeatureValue(value=body_tilt, confidence=confidence, data_kind=DataKind.ESTIMATED),
        shoulder_tilt_deg=None,
        hip_tilt_deg=None,
        left_elbow_angle_deg=None,
        right_elbow_angle_deg=None,
    )


def test_record_pose_features_single_angle_round_trips(tmp_path):
    service = _service(tmp_path)
    session = _setup_account_session(service)
    asset = _media_asset(session.session_id, ShootingAngle.FRONT)
    service.record_media_asset(asset)

    features = _features(body_tilt=5.0, confidence=0.8)
    run_id = service.record_pose_features(asset.media_id, features)

    with SqliteUnitOfWork(service._db_path) as uow:
        stored = uow.pose_features.list_features_by_run(run_id)
    assert stored["body_tilt_deg"]["value"] == pytest.approx(5.0)
    assert stored["body_tilt_deg"]["confidence"] == pytest.approx(0.8)


def test_multi_angle_recording_stores_each_angle_and_merged_report(tmp_path):
    service = _service(tmp_path)
    session = _setup_account_session(service)

    front_asset = _media_asset(session.session_id, ShootingAngle.FRONT)
    side_asset = _media_asset(session.session_id, ShootingAngle.DOMINANT_SIDE)
    service.record_media_asset(front_asset)
    service.record_media_asset(side_asset)

    media_ids_by_angle = {
        ShootingAngle.FRONT: front_asset.media_id,
        ShootingAngle.DOMINANT_SIDE: side_asset.media_id,
    }
    features_by_angle = {
        ShootingAngle.FRONT: _features(body_tilt=5.0, confidence=0.6),
        ShootingAngle.DOMINANT_SIDE: _features(body_tilt=8.0, confidence=0.9),
    }

    result = service.record_multi_angle_pose_analysis(
        session.session_id, media_ids_by_angle, features_by_angle
    )

    assert isinstance(result, MultiAngleRecordingResult)
    assert set(result.per_angle_run_ids) == {ShootingAngle.FRONT, ShootingAngle.DOMINANT_SIDE}

    # Each angle's OWN raw estimate is independently stored and retrievable
    # — merging never destroys the per-angle source data.
    with SqliteUnitOfWork(service._db_path) as uow:
        front_stored = uow.pose_features.list_features_by_run(result.per_angle_run_ids[ShootingAngle.FRONT])
        side_stored = uow.pose_features.list_features_by_run(
            result.per_angle_run_ids[ShootingAngle.DOMINANT_SIDE]
        )
    assert front_stored["body_tilt_deg"]["value"] == pytest.approx(5.0)
    assert side_stored["body_tilt_deg"]["value"] == pytest.approx(8.0)

    # The higher-confidence angle (DOMINANT_SIDE, 0.9) wins the merge, and
    # the merge is never more confident than its best single source.
    merged = result.merge_result.merged["body_tilt_deg"]
    assert merged is not None
    assert merged.value == pytest.approx(8.0)
    assert merged.confidence == pytest.approx(0.9)
    assert merged.source_angle == ShootingAngle.DOMINANT_SIDE
    assert merged.disagreement_deg == pytest.approx(3.0)  # |8.0 - 5.0|


def test_merged_report_persisted_and_readable_back(tmp_path):
    service = _service(tmp_path)
    session = _setup_account_session(service)
    front_asset = _media_asset(session.session_id, ShootingAngle.FRONT)
    service.record_media_asset(front_asset)

    result = service.record_multi_angle_pose_analysis(
        session.session_id,
        {ShootingAngle.FRONT: front_asset.media_id},
        {ShootingAngle.FRONT: _features(body_tilt=4.0, confidence=0.5)},
    )

    with SqliteUnitOfWork(service._db_path) as uow:
        cursor = uow.conn.execute(
            "SELECT session_id, report_json FROM analysis_reports WHERE report_id = ?",
            (result.merged_report_id,),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] == session.session_id
    stored_json = json.loads(row[1])
    assert stored_json["merged"]["body_tilt_deg"]["value"] == pytest.approx(4.0)
    assert stored_json["angles_used"] == ["front"]


def test_empty_features_by_angle_rejected(tmp_path):
    service = _service(tmp_path)
    session = _setup_account_session(service)

    with pytest.raises(ValueError):
        service.record_multi_angle_pose_analysis(session.session_id, {}, {})


def test_missing_media_id_for_an_angle_rejected(tmp_path):
    service = _service(tmp_path)
    session = _setup_account_session(service)
    front_asset = _media_asset(session.session_id, ShootingAngle.FRONT)
    service.record_media_asset(front_asset)

    # features_by_angle names an angle (OPPOSITE_SIDE) that media_ids_by_angle
    # never registered a media asset for — must fail loudly, not silently
    # drop that angle's contribution.
    with pytest.raises(ValueError):
        service.record_multi_angle_pose_analysis(
            session.session_id,
            {ShootingAngle.FRONT: front_asset.media_id},
            {
                ShootingAngle.FRONT: _features(body_tilt=4.0, confidence=0.5),
                ShootingAngle.OPPOSITE_SIDE: _features(body_tilt=6.0, confidence=0.7),
            },
        )


def test_single_angle_contribution_has_no_disagreement(tmp_path):
    service = _service(tmp_path)
    session = _setup_account_session(service)
    front_asset = _media_asset(session.session_id, ShootingAngle.FRONT)
    service.record_media_asset(front_asset)

    result = service.record_multi_angle_pose_analysis(
        session.session_id,
        {ShootingAngle.FRONT: front_asset.media_id},
        {ShootingAngle.FRONT: _features(body_tilt=4.0, confidence=0.5)},
    )

    merged = result.merge_result.merged["body_tilt_deg"]
    assert merged.disagreement_deg is None
    assert merged.contributing_angles == (ShootingAngle.FRONT,)


def test_whole_recording_rolls_back_on_error(tmp_path):
    service = _service(tmp_path)
    session = _setup_account_session(service)
    front_asset = _media_asset(session.session_id, ShootingAngle.FRONT)
    service.record_media_asset(front_asset)

    # A media_id that was never registered violates video_analysis_runs's
    # media_id FK — the whole transaction (both angles' per-run rows, had
    # any already been written) must roll back rather than leaving a
    # partial multi-angle recording on disk.
    with pytest.raises(Exception):
        service.record_multi_angle_pose_analysis(
            session.session_id,
            {ShootingAngle.FRONT: front_asset.media_id, ShootingAngle.DOMINANT_SIDE: "never-registered"},
            {
                ShootingAngle.FRONT: _features(body_tilt=4.0, confidence=0.5),
                ShootingAngle.DOMINANT_SIDE: _features(body_tilt=6.0, confidence=0.7),
            },
        )

    with SqliteUnitOfWork(service._db_path) as uow:
        cursor = uow.conn.execute("SELECT COUNT(*) FROM video_analysis_runs")
        count = cursor.fetchone()[0]
    assert count == 0
