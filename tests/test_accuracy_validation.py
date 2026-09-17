"""Tests for the real-data accuracy comparison tooling (docs §4).

IMPORTANT: these are synthetic-data correctness tests only — they verify
the comparison FORMULAS are right. They are not, and cannot be, a
validation of real DARTSLIVE HOME accuracy (see
dartsanalytics.validation.accuracy module docstring and
docs/reports/release/accuracy-validation.md).
"""

from __future__ import annotations

import pytest

from dartsanalytics.common.enums import DetectionSource, Ring
from dartsanalytics.models.entities import CountupRound, PracticeSession, Throw
from dartsanalytics.validation.accuracy import compare_sessions, compare_throws


def _throw(n, *, score, segment, ring, x=None, y=None, session_id="s", round_id="r") -> Throw:
    return Throw(
        session_id=session_id,
        round_id=round_id,
        round_number=1,
        dart_index=((n - 1) % 3) + 1,
        throw_number_in_session=n,
        detection_source=DetectionSource.DARTSLIVE_HOME,
        score=score,
        segment=segment,
        ring=ring,
        normalized_x=x,
        normalized_y=y,
    )


def _session(throws: list[Throw], *, rounds: list[CountupRound] | None = None) -> PracticeSession:
    s = PracticeSession(account_id="a", player_id="p")
    s.throws.extend(throws)
    if rounds:
        s.rounds.extend(rounds)
    return s


def test_identical_sessions_have_perfect_exact_match():
    throws = [_throw(1, score=60, segment="T20", ring=Ring.TRIPLE)]
    reference = _session(throws)
    candidate = _session([_throw(1, score=60, segment="T20", ring=Ring.TRIPLE)])
    report = compare_sessions(reference, candidate)
    assert report.exact_match_rate == 1.0
    assert report.mean_score_error == 0.0
    assert report.false_positive_count == 0
    assert report.false_negative_count == 0
    assert report.total_score_error == 0


def test_score_error_is_signed_candidate_minus_reference():
    reference = _session([_throw(1, score=20, segment="S20", ring=Ring.SINGLE)])
    candidate = _session([_throw(1, score=60, segment="T20", ring=Ring.TRIPLE)])
    report = compare_sessions(reference, candidate)
    assert report.mean_score_error == pytest.approx(40.0)
    assert report.exact_match_rate == 0.0
    assert report.ring_confusion_rate == 1.0
    assert report.number_confusion_rate == 0.0  # both "20" — same number, different ring


def test_number_confusion_detected_when_ring_matches_but_number_differs():
    reference = _session([_throw(1, score=60, segment="T20", ring=Ring.TRIPLE)])
    candidate = _session([_throw(1, score=57, segment="T19", ring=Ring.TRIPLE)])
    report = compare_sessions(reference, candidate)
    assert report.ring_confusion_rate == 0.0
    assert report.number_confusion_rate == 1.0


def test_false_negative_when_reference_has_throw_candidate_lacks():
    reference = _session([_throw(1, score=25, segment="BULL", ring=Ring.BULL)])
    candidate = _session([])
    report = compare_sessions(reference, candidate)
    assert report.false_negative_count == 1
    assert report.false_positive_count == 0
    assert report.exact_match_rate is None  # nothing to compare (no throw present on both sides)


def test_false_positive_when_candidate_has_extra_throw():
    reference = _session([])
    candidate = _session([_throw(1, score=25, segment="BULL", ring=Ring.BULL)])
    report = compare_sessions(reference, candidate)
    assert report.false_positive_count == 1
    assert report.false_negative_count == 0


def test_coordinate_error_is_euclidean_distance():
    reference = _session([_throw(1, score=25, segment="BULL", ring=Ring.BULL, x=0.0, y=0.0)])
    candidate = _session([_throw(1, score=25, segment="BULL", ring=Ring.BULL, x=0.03, y=0.04)])
    report = compare_sessions(reference, candidate)
    assert report.mean_coordinate_error == pytest.approx(0.05)  # 3-4-5 triangle


def test_bull_vicinity_agreement_rate():
    reference = _session([_throw(1, score=25, segment="BULL", ring=Ring.BULL, x=0.0, y=0.0)])
    candidate = _session([_throw(1, score=0, segment="MISS", ring=Ring.MISS, x=0.9, y=0.9)])
    report = compare_sessions(reference, candidate)
    assert report.bull_vicinity_agreement_rate == 0.0  # reference in vicinity, candidate not


def test_round_score_errors_computed_per_round():
    ref_round = CountupRound(session_id="s", round_id="r1", round_number=1, round_score=60)
    cand_round = CountupRound(session_id="s", round_id="r1", round_number=1, round_score=57)
    reference = _session([], rounds=[ref_round])
    candidate = _session([], rounds=[cand_round])
    report = compare_sessions(reference, candidate)
    assert report.round_score_errors == {1: -3}


def test_total_score_error_sums_all_throws():
    reference = _session([
        _throw(1, score=20, segment="S20", ring=Ring.SINGLE),
        _throw(2, score=20, segment="S20", ring=Ring.SINGLE),
    ])
    candidate = _session([
        _throw(1, score=60, segment="T20", ring=Ring.TRIPLE),
        _throw(2, score=20, segment="S20", ring=Ring.SINGLE),
    ])
    report = compare_sessions(reference, candidate)
    assert report.total_score_reference == 40
    assert report.total_score_candidate == 80
    assert report.total_score_error == 40


def test_compare_throws_handles_both_none_gracefully_via_session_level():
    # compare_throws itself requires at least one side present; exercise
    # the pairwise function directly for the "one side missing" case.
    ref = _throw(1, score=25, segment="BULL", ring=Ring.BULL)
    comparison = compare_throws(ref, None, bull_vicinity_radius=0.15)
    assert comparison.false_negative is True
    assert comparison.exact_match is None
