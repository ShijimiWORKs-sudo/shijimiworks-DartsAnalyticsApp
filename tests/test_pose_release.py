import pytest

from dartsanalytics.pose.release import MAX_HEURISTIC_CONFIDENCE, MIN_HEURISTIC_CONFIDENCE, find_release_candidates


def test_empty_or_single_sample_returns_no_candidates():
    assert find_release_candidates([]) == []
    assert find_release_candidates([(0.0, 0.5, 0.5)]) == []


def test_finds_the_velocity_spike():
    # slow drift, then a fast spike between t=1.0 and t=1.1, then slow again
    track = [
        (0.0, 0.5, 0.5),
        (0.5, 0.51, 0.5),
        (1.0, 0.52, 0.5),
        (1.1, 0.9, 0.9),  # big jump in a short time -> highest velocity
        (1.6, 0.91, 0.9),
        (2.1, 0.92, 0.9),
    ]
    candidates = find_release_candidates(track, top_n=1)
    assert len(candidates) == 1
    assert candidates[0].timestamp_sec == pytest.approx(1.1)


def test_confidence_always_within_documented_bounds():
    track = [(float(i), 0.1 * i, 0.0) for i in range(10)]
    track[5] = (5.0, 5.0, 0.0)  # one big spike
    for candidate in find_release_candidates(track, top_n=5):
        assert MIN_HEURISTIC_CONFIDENCE <= candidate.confidence <= MAX_HEURISTIC_CONFIDENCE


def test_confidence_never_claims_certainty():
    """A heuristic must never report near-1.0 confidence — that would
    misrepresent an unvalidated guess as a measurement."""
    track = [(float(i), (100.0 if i == 3 else 0.0), 0.0) for i in range(6)]
    candidates = find_release_candidates(track, top_n=1)
    assert candidates[0].confidence <= MAX_HEURISTIC_CONFIDENCE
    assert candidates[0].confidence < 0.9


def test_top_n_returns_multiple_ranked_candidates():
    track = [(float(i), float(i % 3), 0.0) for i in range(10)]
    candidates = find_release_candidates(track, top_n=3)
    assert len(candidates) == 3
    velocities = [c.velocity for c in candidates]
    assert velocities == sorted(velocities, reverse=True)


def test_zero_or_negative_time_deltas_are_skipped_not_crashed():
    track = [(1.0, 0.0, 0.0), (1.0, 5.0, 5.0), (2.0, 5.1, 5.1)]  # duplicate timestamp
    candidates = find_release_candidates(track, top_n=1)
    assert len(candidates) == 1  # only the valid (dt>0) segment counts


def test_rejects_invalid_top_n():
    with pytest.raises(ValueError):
        find_release_candidates([(0.0, 0, 0), (1.0, 1, 1)], top_n=0)
