"""Late-round degradation comparison (docs §12 item 7 ラウンド後半での偏り;
docs §20 比較指標もこの種の比較を参照: "ラウンド後半の崩れ").

Splits a session's throws into an early half and a late half by round
number and compares score average + dispersion (dartsanalytics.board.
grouping) between them. This is a CALCULATED comparison over measured/
coordinate data — it does NOT assert a cause. "Degradation" here means
only "the late half scored lower / spread out more than the early half",
a factual comparison; turning that into a cause candidate (fatigue, form
breakdown, etc.) is explicitly the separate, more conservative job of
dartsanalytics.integrated.causes (docs §16 原因推定のルール).

A session with fewer than 2 distinct rounds, or with no board-coordinate
data at all, cannot support this comparison — `insufficient_data=True` is
returned rather than fabricating one (解析不能なものを無理に判定しない).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dartsanalytics.board.grouping import GroupingStats, compute_grouping_stats
from dartsanalytics.models.entities import PracticeSession, Throw


@dataclass(frozen=True)
class LateRoundComparison:
    early_rounds: list[int]
    late_rounds: list[int]
    early_score_average: float | None
    late_score_average: float | None
    score_delta: float | None  # late - early; negative = late rounds scored lower
    early_dispersion: GroupingStats | None
    late_dispersion: GroupingStats | None
    insufficient_data: bool

    def to_dict(self) -> dict:
        return {
            "early_rounds": self.early_rounds,
            "late_rounds": self.late_rounds,
            "early_score_average": self.early_score_average,
            "late_score_average": self.late_score_average,
            "score_delta": self.score_delta,
            "early_dispersion": self.early_dispersion.to_dict() if self.early_dispersion else None,
            "late_dispersion": self.late_dispersion.to_dict() if self.late_dispersion else None,
            "insufficient_data": self.insufficient_data,
        }


def _score_average(throws: list[Throw]) -> float | None:
    scored = [t.score for t in throws if t.score is not None]
    return (sum(scored) / len(scored)) if scored else None


def _dispersion_or_none(throws: list[Throw]) -> GroupingStats | None:
    points = [(t.normalized_x, t.normalized_y) for t in throws if t.normalized_x is not None and t.normalized_y is not None]
    return compute_grouping_stats(points) if points else None


def compare_early_vs_late_rounds(session: PracticeSession) -> LateRoundComparison:
    rounds_present = sorted({t.round_number for t in session.throws})

    if len(rounds_present) < 2:
        return LateRoundComparison(
            early_rounds=[],
            late_rounds=[],
            early_score_average=None,
            late_score_average=None,
            score_delta=None,
            early_dispersion=None,
            late_dispersion=None,
            insufficient_data=True,
        )

    # Odd round counts give the earlier half the extra round (e.g. 5
    # rounds -> 3 early / 2 late) — an arbitrary but documented, consistent
    # convention rather than an unstated one.
    early_count = math.ceil(len(rounds_present) / 2)
    early_rounds = rounds_present[:early_count]
    late_rounds = rounds_present[early_count:]

    early_throws = [t for t in session.throws if t.round_number in early_rounds]
    late_throws = [t for t in session.throws if t.round_number in late_rounds]

    early_avg = _score_average(early_throws)
    late_avg = _score_average(late_throws)
    delta = (late_avg - early_avg) if (early_avg is not None and late_avg is not None) else None

    return LateRoundComparison(
        early_rounds=early_rounds,
        late_rounds=late_rounds,
        early_score_average=early_avg,
        late_score_average=late_avg,
        score_delta=delta,
        early_dispersion=_dispersion_or_none(early_throws),
        late_dispersion=_dispersion_or_none(late_throws),
        insufficient_data=False,
    )
