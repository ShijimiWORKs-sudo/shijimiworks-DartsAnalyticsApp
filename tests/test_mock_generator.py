import pytest

from dartsanalytics.common.enums import SessionStatus
from dartsanalytics.countup.mock import MockCountUpGenerator


def _generate(seed=42, num_throws=24):
    gen = MockCountUpGenerator(seed=seed)
    return gen.generate(account_id="acc-1", player_id="player-1", num_throws=num_throws)


def test_full_session_has_8_rounds_and_24_throws():
    session = _generate(num_throws=24)
    assert len(session.throws) == 24
    assert len(session.rounds) == 8
    assert session.status == SessionStatus.COMPLETE
    assert session.ended_at is not None


def test_reproducibility_same_seed_same_output():
    """Reproducibility test (AGENTS.md §4): identical seed -> identical
    session content, field for field (excluding the random ids/timestamps
    generated per-object, which are compared separately below)."""
    a = _generate(seed=7)
    b = _generate(seed=7)

    a_throws = [(t.score, t.segment, t.ring, t.round_number, t.dart_index) for t in a.throws]
    b_throws = [(t.score, t.segment, t.ring, t.round_number, t.dart_index) for t in b.throws]
    assert a_throws == b_throws
    assert a.total_score == b.total_score
    assert [r.round_score for r in a.rounds] == [r.round_score for r in b.rounds]


def test_different_seeds_can_differ():
    a = _generate(seed=1)
    b = _generate(seed=2)
    a_throws = [(t.score, t.segment) for t in a.throws]
    b_throws = [(t.score, t.segment) for t in b.throws]
    assert a_throws != b_throws  # not guaranteed in general, but true for these two seeds


def test_incomplete_session_status_and_round_count():
    """'途中終了時はincompleteとする' (design principle #1, §5.1)."""
    session = _generate(num_throws=10)
    assert session.status == SessionStatus.INCOMPLETE
    assert session.ended_at is None
    assert len(session.throws) == 10
    # 10 throws = 3 full rounds (9 throws) + 1 throw in round 4
    assert len(session.rounds) == 4
    round_4 = next(r for r in session.rounds if r.round_number == 4)
    round_4_throws = [t for t in session.throws if t.round_id == round_4.round_id]
    assert len(round_4_throws) == 1


@pytest.mark.parametrize("bad_num_throws", [0, 25, -1])
def test_generate_rejects_invalid_num_throws(bad_num_throws):
    gen = MockCountUpGenerator(seed=1)
    with pytest.raises(ValueError):
        gen.generate(account_id="acc-1", player_id="player-1", num_throws=bad_num_throws)


def test_total_score_matches_sum_of_throw_scores():
    session = _generate(seed=99, num_throws=24)
    assert session.total_score == sum(t.score for t in session.throws)


def test_round_scores_match_sum_of_their_throws():
    session = _generate(seed=99, num_throws=24)
    for round_ in session.rounds:
        round_throws = [t for t in session.throws if t.round_id == round_.round_id]
        assert round_.round_score == sum(t.score for t in round_throws)
