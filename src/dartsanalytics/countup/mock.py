"""Mock COUNT-UP session generator.

Phase 1 explicitly does not require a real DARTSLIVE HOME connection yet
(docs/codex/...md §Phase1: "DARTSLIVE HOMEはまだ必須にしない。まずモックデータ
で完全に再現できる状態を作る。"). This generator produces a full 8-round /
24-throw COUNT-UP session (or a shorter, `incomplete` one) with deterministic
output for a given seed — reproducibility is a Phase-wide test requirement
(AGENTS.md §4).

Every throw here is tagged DataKind.MEASURED / DetectionSource.MOCK: it
stands in for "a real measurement would go here", not for a model's
estimate, so it deliberately does NOT carry a confidence score (see
docs §9 / common/confidence.py — only ESTIMATED/ADVICE data requires one).
"""

from __future__ import annotations

import random

from dartsanalytics.common.enums import DataKind, DetectionSource, GameType, Ring, SessionStatus
from dartsanalytics.countup.scoring import BOARD_NUMBERS, format_segment, score_for
from dartsanalytics.models.entities import CountupRound, PracticeSession, Throw

# Rough weighting so mock sessions look plausible (most darts land in a
# single segment, bulls and misses are rarer) — this is flavor for
# testing/demo purposes only, not a claim about real player behavior.
_RING_WEIGHTS: list[tuple[Ring, float]] = [
    (Ring.SINGLE, 0.55),
    (Ring.DOUBLE, 0.12),
    (Ring.TRIPLE, 0.18),
    (Ring.BULL, 0.05),
    (Ring.DBULL, 0.03),
    (Ring.MISS, 0.07),
]


class MockCountUpGenerator:
    """Deterministic (seeded) generator for mock COUNT-UP sessions."""

    def __init__(self, seed: int):
        self.seed = seed
        self._rng = random.Random(seed)

    def _random_ring(self) -> Ring:
        rings, weights = zip(*_RING_WEIGHTS)
        return self._rng.choices(rings, weights=weights, k=1)[0]

    def _random_throw_values(self) -> tuple[Ring, int | None]:
        ring = self._random_ring()
        if ring in (Ring.BULL, Ring.DBULL, Ring.MISS):
            return ring, None
        number = self._rng.choice(BOARD_NUMBERS)
        return ring, number

    def generate(
        self,
        account_id: str,
        player_id: str,
        *,
        num_throws: int = 24,
        equipment_id: str | None = None,
    ) -> PracticeSession:
        """Generate a session with `num_throws` throws (1..24).

        `num_throws` < 24 simulates a session ended early (design principle
        #1 §5.1: "途中終了時はincompleteとする").
        """
        if not 1 <= num_throws <= 24:
            raise ValueError(f"num_throws must be 1..24, got {num_throws}")

        session = PracticeSession(
            account_id=account_id,
            player_id=player_id,
            equipment_id=equipment_id,
            game_type=GameType.COUNT_UP,
            status=SessionStatus.COMPLETE if num_throws == 24 else SessionStatus.INCOMPLETE,
        )

        rounds_by_number: dict[int, CountupRound] = {}
        for i in range(num_throws):
            throw_number_in_session = i + 1
            round_number = i // 3 + 1
            dart_index = i % 3 + 1

            if round_number not in rounds_by_number:
                rounds_by_number[round_number] = CountupRound(
                    session_id=session.session_id, round_number=round_number
                )
                session.rounds.append(rounds_by_number[round_number])
            round_ = rounds_by_number[round_number]

            ring, number = self._random_throw_values()
            score = score_for(ring, number)
            throw = Throw(
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
            session.throws.append(throw)

        # Round scores are a deterministic calculation over measured throws
        # (DataKind.CALCULATED would apply if we stored them as their own
        # graded record; here they're just a derived field on the round).
        for round_ in session.rounds:
            round_throws = [t for t in session.throws if t.round_id == round_.round_id]
            round_.round_score = sum(t.score or 0 for t in round_throws)

        session.total_score = sum(t.score or 0 for t in session.throws)
        if session.status == SessionStatus.COMPLETE:
            session.ended_at = session.throws[-1].created_at

        return session
