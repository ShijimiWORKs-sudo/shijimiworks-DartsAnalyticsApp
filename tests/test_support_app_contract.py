import json

import pytest

from dartsanalytics.common.enums import DataKind, DetectionSource, GameType, Ring, SyncState
from dartsanalytics.contract.support_app import (
    DEFAULT_ANALYSIS_VERSION,
    build_support_app_record,
    build_support_app_records,
    export_support_app_json,
    write_support_app_json,
)
from dartsanalytics.models.entities import PracticeSession, Throw


def _session_with_throws(n=3) -> PracticeSession:
    session = PracticeSession(account_id="acct-1", player_id="player-1", game_type=GameType.COUNT_UP, practice_type="free")
    throws = []
    for i in range(n):
        t = Throw(
            session_id=session.session_id,
            round_id="r1",
            round_number=1,
            dart_index=(i % 3) + 1,
            throw_number_in_session=i + 1,
            detection_source=DetectionSource.MOCK,
            data_kind=DataKind.MEASURED,
            score=20,
            ring=Ring.TRIPLE,
            normalized_x=0.1,
            normalized_y=0.2,
        )
        throws.append(t)
    session.throws = throws
    return session


def test_build_record_maps_fields_correctly():
    session = _session_with_throws(1)
    throw = session.throws[0]
    record = build_support_app_record(session, throw)

    assert record.account_id == session.account_id
    assert record.player_id == session.player_id
    assert record.game_session_id == session.session_id
    assert record.record_id == throw.throw_id
    assert record.game_type == "COUNT_UP"
    assert record.ring == "TRIPLE"
    assert record.normalized_x == pytest.approx(0.1)
    assert record.normalized_y == pytest.approx(0.2)
    assert record.sync_state == SyncState.PENDING.value
    assert record.analysis_version == DEFAULT_ANALYSIS_VERSION
    assert record.practice_menu_id is None


def test_practice_menu_id_and_sync_state_and_analysis_version_pass_through():
    session = _session_with_throws(1)
    throw = session.throws[0]
    record = build_support_app_record(
        session,
        throw,
        practice_menu_id="menu-42",
        sync_state=SyncState.SYNCED,
        analysis_version="board_calib_v1",
    )
    assert record.practice_menu_id == "menu-42"
    assert record.sync_state == "synced"
    assert record.analysis_version == "board_calib_v1"


def test_rejects_throw_from_a_different_session():
    session = _session_with_throws(1)
    other_session = _session_with_throws(1)
    with pytest.raises(ValueError):
        build_support_app_record(session, other_session.throws[0])


def test_distance_from_bull_computed_when_missing_but_coordinates_present():
    session = _session_with_throws(1)
    throw = session.throws[0]
    throw.distance_from_bull = None  # force computation from normalized_x/y
    record = build_support_app_record(session, throw)
    assert record.distance_from_bull == pytest.approx((0.1**2 + 0.2**2) ** 0.5)


def test_missing_coordinates_yield_none_not_a_guess():
    session = _session_with_throws(0)
    throw = Throw(
        session_id=session.session_id,
        round_id="r1",
        round_number=1,
        dart_index=1,
        throw_number_in_session=1,
        detection_source=DetectionSource.MOCK,
        data_kind=DataKind.MEASURED,
        score=20,
        ring=Ring.MISS,
    )
    session.throws = [throw]
    record = build_support_app_record(session, throw)
    assert record.normalized_x is None
    assert record.normalized_y is None
    assert record.distance_from_bull is None


def test_build_records_covers_every_throw_in_session():
    session = _session_with_throws(5)
    records = build_support_app_records(session)
    assert len(records) == 5
    assert {r.record_id for r in records} == {t.throw_id for t in session.throws}


def test_export_json_round_trips():
    session = _session_with_throws(3)
    text = export_support_app_json(session, practice_menu_id="menu-1")
    parsed = json.loads(text)
    assert len(parsed) == 3
    assert parsed[0]["practice_menu_id"] == "menu-1"
    assert parsed[0]["account_id"] == session.account_id


def test_write_support_app_json_creates_file(tmp_path):
    session = _session_with_throws(2)
    out_path = tmp_path / "nested" / "support.json"
    written = write_support_app_json(session, out_path)
    assert written == out_path
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(data) == 2
