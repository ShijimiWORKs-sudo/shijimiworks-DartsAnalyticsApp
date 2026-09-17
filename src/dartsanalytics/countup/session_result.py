"""Session result summary — a CALCULATED view over a session's raw throws.

Kept as a pure function over PracticeSession rather than a stored/mutable
field, so it's always reproducible from the raw per-throw data (design
principle #2: 1投単位の生データを保存する — the summary is derived, not
the source of truth).
"""

from __future__ import annotations

from dataclasses import dataclass

from dartsanalytics.common.enums import Ring, SessionStatus
from dartsanalytics.models.entities import PracticeSession


@dataclass(frozen=True)
class SessionResult:
    session_id: str
    status: SessionStatus
    throw_count: int
    total_score: int
    round_scores: list[int]
    round_average: float | None
    throw_average: float | None
    ring_counts: dict[str, int]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "throw_count": self.throw_count,
            "total_score": self.total_score,
            "round_scores": self.round_scores,
            "round_average": self.round_average,
            "throw_average": self.throw_average,
            "ring_counts": self.ring_counts,
        }


def summarize(session: PracticeSession) -> SessionResult:
    throws = session.throws
    throw_count = len(throws)
    total_score = sum(t.score or 0 for t in throws)

    round_scores = [r.round_score or 0 for r in sorted(session.rounds, key=lambda r: r.round_number)]

    ring_counts: dict[str, int] = {ring.value: 0 for ring in Ring}
    for t in throws:
        if t.ring is not None:
            ring_counts[t.ring.value] += 1

    round_average = (sum(round_scores) / len(round_scores)) if round_scores else None
    throw_average = (total_score / throw_count) if throw_count else None

    return SessionResult(
        session_id=session.session_id,
        status=session.status,
        throw_count=throw_count,
        total_score=total_score,
        round_scores=round_scores,
        round_average=round_average,
        throw_average=throw_average,
        ring_counts=ring_counts,
    )
