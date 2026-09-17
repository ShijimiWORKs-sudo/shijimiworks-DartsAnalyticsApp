"""Fixed COUNT-UP throw-sequence fixtures for deterministic tests.

AGENTS.md §4 asks for fixed fixtures covering edge cases. The spatial
fixtures listed there (all-center / all-high / all-low / left-right split /
one outlier) describe board-coordinate distributions and belong to Phase 3
(board coordinate / grouping analysis), where actual x/y coordinates exist.
Phase 1 only has scores/rings (no coordinates yet), so these fixtures cover
the Phase-1-relevant edge cases instead: uniform ring patterns, a session
with missing throws ("24投中数投欠損"), and one high-value outlier throw
among low ones.
"""

from __future__ import annotations

from dartsanalytics.common.enums import DataKind, DetectionSource, GameType, Ring, SessionStatus
from dartsanalytics.countup.scoring import format_segment, score_for
from dartsanalytics.models.entities import Account, CountupRound, Player, PracticeSession, Throw


def build_session(
    rings_and_numbers: list[tuple[Ring, int | None]],
    *,
    status: SessionStatus | None = None,
) -> PracticeSession:
    """Deterministically build a session from an explicit throw sequence.

    Unlike MockCountUpGenerator (randomized-but-seeded), this gives exact
    control over content for edge-case fixtures.
    """
    if not 1 <= len(rings_and_numbers) <= 24:
        raise ValueError("fixture must specify 1..24 throws")

    account = Account(display_name="fixture-account")
    player = Player(account_id=account.account_id, display_name="fixture-player")
    session = PracticeSession(
        account_id=account.account_id,
        player_id=player.player_id,
        game_type=GameType.COUNT_UP,
        status=status
        or (SessionStatus.COMPLETE if len(rings_and_numbers) == 24 else SessionStatus.INCOMPLETE),
    )

    rounds_by_number: dict[int, CountupRound] = {}
    for i, (ring, number) in enumerate(rings_and_numbers):
        throw_number_in_session = i + 1
        round_number = i // 3 + 1
        dart_index = i % 3 + 1

        if round_number not in rounds_by_number:
            rounds_by_number[round_number] = CountupRound(
                session_id=session.session_id, round_number=round_number
            )
            session.rounds.append(rounds_by_number[round_number])
        round_ = rounds_by_number[round_number]

        score = score_for(ring, number)
        session.throws.append(
            Throw(
                session_id=session.session_id,
                round_id=round_.round_id,
                round_number=round_number,
                dart_index=dart_index,
                throw_number_in_session=throw_number_in_session,
                detection_source=DetectionSource.MOCK,
                data_kind=DataKind.MEASURED,
                score=score,
                segment=format_segment(ring, number),
                ring=ring,
                actual_target=format_segment(ring, number),
            )
        )

    for round_ in session.rounds:
        round_throws = [t for t in session.throws if t.round_id == round_.round_id]
        round_.round_score = sum(t.score or 0 for t in round_throws)

    session.total_score = sum(t.score or 0 for t in session.throws)
    return session


def all_miss_session() -> PracticeSession:
    return build_session([(Ring.MISS, None)] * 24)


def all_dbull_session() -> PracticeSession:
    return build_session([(Ring.DBULL, None)] * 24)


def missing_throws_session(num_throws: int = 17) -> PracticeSession:
    """'24投中数投欠損' — a session that ended before all 24 darts were thrown."""
    return build_session([(Ring.SINGLE, 5)] * num_throws, status=SessionStatus.INCOMPLETE)


def one_outlier_session() -> PracticeSession:
    """23 low-value throws plus one maximum-value (DBULL) outlier."""
    throws = [(Ring.SINGLE, 1)] * 23 + [(Ring.DBULL, None)]
    return build_session(throws)
