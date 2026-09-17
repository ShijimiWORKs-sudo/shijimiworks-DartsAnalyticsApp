"""Real COUNT-UP data accuracy validation tooling (docs §4).

Compares a REFERENCE session against a CANDIDATE session for the SAME
actual game, throw-by-throw (matched by throw_number_in_session). Typical
use: reference = throws recorded via the DARTSLIVE HOME BLE adapter
(Phase 2, DetectionSource.DARTSLIVE_HOME), candidate = throws detected by
this app's own board-camera pipeline (Phase 3+, DetectionSource.
BOARD_CAMERA) — but the module itself is source-agnostic; it only compares
two PracticeSession objects.

docs §4, verbatim caveat this module honors: "DARTSLIVE HOME側のグラフ等
から得られる値は「完全なground truth」と断定せず、取得可能な範囲を明記
する。" Accordingly this module calls its first argument `reference`, not
`ground_truth`, throughout — even the DARTSLIVE HOME side is a reference
measurement with its own possible error, not an infallible oracle.

Status (docs §14/§15: implement ahead of the blocking real-data
requirement, so the tool is ready the moment data arrives): this module is
implemented and tested against SYNTHETIC session pairs only. It has never
been run against real DARTSLIVE HOME data — that requires the user to
supply 10-30 real games (see docs/reports/release/accuracy-validation.md),
which this session does not have. The numbers this module PRODUCES are
only meaningful once run against real data; the module's own CORRECTNESS
(does it compute the right formula) is what the synthetic tests establish.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dartsanalytics.board.grouping import DEFAULT_BULL_VICINITY_RADIUS
from dartsanalytics.models.entities import PracticeSession, Throw


@dataclass(frozen=True)
class ThrowComparison:
    throw_number_in_session: int
    reference_score: int | None
    candidate_score: int | None
    score_error: int | None  # candidate - reference (signed); None if either side missing
    exact_match: bool | None  # score match; None if either side missing
    reference_segment: str | None
    candidate_segment: str | None
    number_confusion: bool | None  # both present, both non-BULL/MISS, same ring but different number
    ring_confusion: bool | None  # both present, ring differs (SINGLE vs DOUBLE vs TRIPLE vs BULL vs MISS)
    coordinate_error: float | None  # euclidean distance in normalized coords; None if either lacks coords
    reference_bull_vicinity: bool | None
    candidate_bull_vicinity: bool | None
    false_positive: bool  # candidate has a throw at this slot, reference does not
    false_negative: bool  # reference has a throw at this slot, candidate does not

    def to_dict(self) -> dict:
        return {
            "throw_number_in_session": self.throw_number_in_session,
            "reference_score": self.reference_score,
            "candidate_score": self.candidate_score,
            "score_error": self.score_error,
            "exact_match": self.exact_match,
            "reference_segment": self.reference_segment,
            "candidate_segment": self.candidate_segment,
            "number_confusion": self.number_confusion,
            "ring_confusion": self.ring_confusion,
            "coordinate_error": self.coordinate_error,
            "reference_bull_vicinity": self.reference_bull_vicinity,
            "candidate_bull_vicinity": self.candidate_bull_vicinity,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
        }


@dataclass(frozen=True)
class AccuracyReport:
    n_reference_throws: int
    n_candidate_throws: int
    n_both_present: int  # throws where both sides have data — the denominator for match-rate metrics
    exact_match_rate: float | None
    mean_score_error: float | None  # signed; positive = candidate overestimates
    mean_abs_score_error: float | None
    mean_coordinate_error: float | None
    false_positive_count: int
    false_negative_count: int
    ring_confusion_rate: float | None
    number_confusion_rate: float | None
    bull_vicinity_agreement_rate: float | None
    total_score_reference: int
    total_score_candidate: int
    total_score_error: int
    round_score_errors: dict[int, int | None] = field(default_factory=dict)
    throw_comparisons: list[ThrowComparison] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "n_reference_throws": self.n_reference_throws,
            "n_candidate_throws": self.n_candidate_throws,
            "n_both_present": self.n_both_present,
            "exact_match_rate": self.exact_match_rate,
            "mean_score_error": self.mean_score_error,
            "mean_abs_score_error": self.mean_abs_score_error,
            "mean_coordinate_error": self.mean_coordinate_error,
            "false_positive_count": self.false_positive_count,
            "false_negative_count": self.false_negative_count,
            "ring_confusion_rate": self.ring_confusion_rate,
            "number_confusion_rate": self.number_confusion_rate,
            "bull_vicinity_agreement_rate": self.bull_vicinity_agreement_rate,
            "total_score_reference": self.total_score_reference,
            "total_score_candidate": self.total_score_candidate,
            "total_score_error": self.total_score_error,
            "round_score_errors": self.round_score_errors,
            "throw_comparisons": [c.to_dict() for c in self.throw_comparisons],
        }


def _index_throws(session: PracticeSession) -> dict[int, Throw]:
    return {t.throw_number_in_session: t for t in session.throws}


def _bull_vicinity(throw: Throw, *, radius: float) -> bool | None:
    if throw.normalized_x is None or throw.normalized_y is None:
        return None
    distance = (throw.normalized_x**2 + throw.normalized_y**2) ** 0.5
    return distance <= radius


def _number_from_segment(segment: str | None) -> str | None:
    """Extract the number part of a segment label ('T20' -> '20', 'BULL' ->
    None — BULL/DBULL/MISS have no number to confuse)."""
    if segment is None or segment in ("BULL", "DBULL", "MISS"):
        return None
    return segment[1:] if segment and segment[0] in "SDT" else segment


def _ring_from_segment(segment: str | None) -> str | None:
    if segment is None:
        return None
    if segment in ("BULL", "DBULL", "MISS"):
        return segment
    return segment[0] if segment and segment[0] in "SDT" else None


def compare_throws(
    reference: Throw | None, candidate: Throw | None, *, bull_vicinity_radius: float
) -> ThrowComparison:
    throw_number = (reference or candidate).throw_number_in_session  # type: ignore[union-attr]

    if reference is None or candidate is None:
        return ThrowComparison(
            throw_number_in_session=throw_number,
            reference_score=reference.score if reference else None,
            candidate_score=candidate.score if candidate else None,
            score_error=None,
            exact_match=None,
            reference_segment=reference.segment if reference else None,
            candidate_segment=candidate.segment if candidate else None,
            number_confusion=None,
            ring_confusion=None,
            coordinate_error=None,
            reference_bull_vicinity=(
                _bull_vicinity(reference, radius=bull_vicinity_radius) if reference else None
            ),
            candidate_bull_vicinity=(
                _bull_vicinity(candidate, radius=bull_vicinity_radius) if candidate else None
            ),
            false_positive=reference is None and candidate is not None,
            false_negative=reference is not None and candidate is None,
        )

    score_error = None
    exact_match = None
    if reference.score is not None and candidate.score is not None:
        score_error = candidate.score - reference.score
        exact_match = score_error == 0

    ref_ring = _ring_from_segment(reference.segment)
    cand_ring = _ring_from_segment(candidate.segment)
    ring_confusion = None
    if ref_ring is not None and cand_ring is not None:
        ring_confusion = ref_ring != cand_ring

    ref_number = _number_from_segment(reference.segment)
    cand_number = _number_from_segment(candidate.segment)
    number_confusion = None
    if ref_number is not None and cand_number is not None:
        number_confusion = ref_number != cand_number

    coordinate_error = None
    if (
        reference.normalized_x is not None
        and reference.normalized_y is not None
        and candidate.normalized_x is not None
        and candidate.normalized_y is not None
    ):
        coordinate_error = (
            (reference.normalized_x - candidate.normalized_x) ** 2
            + (reference.normalized_y - candidate.normalized_y) ** 2
        ) ** 0.5

    return ThrowComparison(
        throw_number_in_session=throw_number,
        reference_score=reference.score,
        candidate_score=candidate.score,
        score_error=score_error,
        exact_match=exact_match,
        reference_segment=reference.segment,
        candidate_segment=candidate.segment,
        number_confusion=number_confusion,
        ring_confusion=ring_confusion,
        coordinate_error=coordinate_error,
        reference_bull_vicinity=_bull_vicinity(reference, radius=bull_vicinity_radius),
        candidate_bull_vicinity=_bull_vicinity(candidate, radius=bull_vicinity_radius),
        false_positive=False,
        false_negative=False,
    )


def _round_scores(session: PracticeSession) -> dict[int, int | None]:
    return {r.round_number: r.round_score for r in session.rounds}


def compare_sessions(
    reference: PracticeSession,
    candidate: PracticeSession,
    *,
    bull_vicinity_radius: float = DEFAULT_BULL_VICINITY_RADIUS,
) -> AccuracyReport:
    """`reference`/`candidate` should be two recordings of the SAME actual
    game (same throw sequence), e.g. one from DARTSLIVE HOME BLE and one
    from this app's board-camera detection. throw_number_in_session is the
    join key — no attempt is made to realign a shifted/misordered
    sequence (a shift itself is a finding worth surfacing as false
    positives/negatives, not something to silently correct for)."""
    ref_throws = _index_throws(reference)
    cand_throws = _index_throws(candidate)
    all_numbers = sorted(set(ref_throws) | set(cand_throws))

    comparisons = [
        compare_throws(
            ref_throws.get(n), cand_throws.get(n), bull_vicinity_radius=bull_vicinity_radius
        )
        for n in all_numbers
    ]

    both_present = [c for c in comparisons if not c.false_positive and not c.false_negative]
    n_both = len(both_present)

    exact_matches = [c for c in both_present if c.exact_match is not None]
    exact_match_rate = (
        sum(1 for c in exact_matches if c.exact_match) / len(exact_matches) if exact_matches else None
    )

    score_errors = [c.score_error for c in both_present if c.score_error is not None]
    mean_score_error = sum(score_errors) / len(score_errors) if score_errors else None
    mean_abs_score_error = (
        sum(abs(e) for e in score_errors) / len(score_errors) if score_errors else None
    )

    coord_errors = [c.coordinate_error for c in both_present if c.coordinate_error is not None]
    mean_coordinate_error = sum(coord_errors) / len(coord_errors) if coord_errors else None

    ring_judged = [c.ring_confusion for c in both_present if c.ring_confusion is not None]
    ring_confusion_rate = sum(ring_judged) / len(ring_judged) if ring_judged else None

    number_judged = [c.number_confusion for c in both_present if c.number_confusion is not None]
    number_confusion_rate = sum(number_judged) / len(number_judged) if number_judged else None

    bull_vicinity_judged = [
        c for c in both_present
        if c.reference_bull_vicinity is not None and c.candidate_bull_vicinity is not None
    ]
    bull_vicinity_agreement_rate = (
        sum(1 for c in bull_vicinity_judged if c.reference_bull_vicinity == c.candidate_bull_vicinity)
        / len(bull_vicinity_judged)
        if bull_vicinity_judged
        else None
    )

    false_positive_count = sum(1 for c in comparisons if c.false_positive)
    false_negative_count = sum(1 for c in comparisons if c.false_negative)

    total_ref = sum(t.score or 0 for t in reference.throws)
    total_cand = sum(t.score or 0 for t in candidate.throws)

    ref_rounds = _round_scores(reference)
    cand_rounds = _round_scores(candidate)
    round_errors: dict[int, int | None] = {}
    for round_number in sorted(set(ref_rounds) | set(cand_rounds)):
        r = ref_rounds.get(round_number)
        c = cand_rounds.get(round_number)
        round_errors[round_number] = (c - r) if (r is not None and c is not None) else None

    return AccuracyReport(
        n_reference_throws=len(reference.throws),
        n_candidate_throws=len(candidate.throws),
        n_both_present=n_both,
        exact_match_rate=exact_match_rate,
        mean_score_error=mean_score_error,
        mean_abs_score_error=mean_abs_score_error,
        mean_coordinate_error=mean_coordinate_error,
        false_positive_count=false_positive_count,
        false_negative_count=false_negative_count,
        ring_confusion_rate=ring_confusion_rate,
        number_confusion_rate=number_confusion_rate,
        bull_vicinity_agreement_rate=bull_vicinity_agreement_rate,
        total_score_reference=total_ref,
        total_score_candidate=total_cand,
        total_score_error=total_cand - total_ref,
        round_score_errors=round_errors,
        throw_comparisons=comparisons,
    )
