"""Phase 0 tests for the common entity dataclasses."""

import pytest

from dartsanalytics.common.confidence import MissingConfidenceError
from dartsanalytics.common.enums import DataKind, DetectionSource, Ring
from dartsanalytics.models import Account, CountupRound, Player, PracticeSession, Throw


def test_account_round_trip():
    acc = Account(display_name="洋典")
    data = acc.to_dict()
    restored = Account.from_dict(data)
    assert restored == acc


def test_player_invalid_dominant_hand_rejected():
    acc = Account(display_name="洋典")
    with pytest.raises(ValueError):
        Player(account_id=acc.account_id, display_name="Player 1", dominant_hand="ambidextrous")


def test_countup_round_number_bounds():
    with pytest.raises(ValueError):
        CountupRound(session_id="s1", round_number=0)
    with pytest.raises(ValueError):
        CountupRound(session_id="s1", round_number=9)
    CountupRound(session_id="s1", round_number=8)  # no raise


def test_throw_requires_confidence_when_estimated():
    with pytest.raises(MissingConfidenceError):
        Throw(
            session_id="s1",
            round_id="r1",
            round_number=1,
            dart_index=1,
            throw_number_in_session=1,
            detection_source=DetectionSource.BOARD_CAMERA,
            data_kind=DataKind.ESTIMATED,
            confidence=None,
        )


def test_throw_measured_default_needs_no_confidence():
    t = Throw(
        session_id="s1",
        round_id="r1",
        round_number=1,
        dart_index=1,
        throw_number_in_session=1,
        detection_source=DetectionSource.DARTSLIVE_HOME,
        score=50,
        ring=Ring.DBULL,
    )
    assert t.confidence is None
    assert t.data_kind is DataKind.MEASURED


def test_throw_round_trip_preserves_enums():
    t = Throw(
        session_id="s1",
        round_id="r1",
        round_number=1,
        dart_index=2,
        throw_number_in_session=2,
        detection_source=DetectionSource.MOCK,
        data_kind=DataKind.ESTIMATED,
        confidence=0.97,
        ring=Ring.TRIPLE,
        segment="T20",
        score=60,
    )
    data = t.to_dict()
    assert data["detection_source"] == "mock"
    assert data["ring"] == "TRIPLE"
    restored = Throw.from_dict(data)
    assert restored.detection_source is DetectionSource.MOCK
    assert restored.ring is Ring.TRIPLE
    assert restored == t


@pytest.mark.parametrize("bad_index", [0, 4])
def test_throw_dart_index_bounds(bad_index):
    with pytest.raises(ValueError):
        Throw(
            session_id="s1",
            round_id="r1",
            round_number=1,
            dart_index=bad_index,
            throw_number_in_session=1,
            detection_source=DetectionSource.MOCK,
        )


@pytest.mark.parametrize("bad_number", [0, 25])
def test_throw_number_in_session_bounds(bad_number):
    with pytest.raises(ValueError):
        Throw(
            session_id="s1",
            round_id="r1",
            round_number=1,
            dart_index=1,
            throw_number_in_session=bad_number,
            detection_source=DetectionSource.MOCK,
        )


def test_practice_session_round_trip_with_children():
    acc = Account(display_name="洋典")
    player = Player(account_id=acc.account_id, display_name="Player 1")
    session = PracticeSession(account_id=acc.account_id, player_id=player.player_id)
    session.rounds.append(CountupRound(session_id=session.session_id, round_number=1))
    session.throws.append(
        Throw(
            session_id=session.session_id,
            round_id=session.rounds[0].round_id,
            round_number=1,
            dart_index=1,
            throw_number_in_session=1,
            detection_source=DetectionSource.MOCK,
            score=20,
        )
    )
    data = session.to_dict()
    restored = PracticeSession.from_dict(data)
    assert restored.session_id == session.session_id
    assert len(restored.rounds) == 1
    assert len(restored.throws) == 1
    assert restored.throws[0].score == 20
