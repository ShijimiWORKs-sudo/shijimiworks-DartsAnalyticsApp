import pytest

from dartsanalytics.advisor.generate import BANNED_ABSOLUTE_PHRASES, build_advisor_output
from dartsanalytics.board.grouping import compute_grouping_stats
from dartsanalytics.common.enums import DataKind
from dartsanalytics.experiments.decision import Decision
from dartsanalytics.experiments.models import Experiment
from dartsanalytics.integrated.causes import CandidateCause
from dartsanalytics.integrated.frequent_segments import DirectionStreaks, FrequentSegmentStats
from dartsanalytics.integrated.late_round import LateRoundComparison
from dartsanalytics.integrated.report import IntegratedAnalysisReport


def _minimal_report(*, dispersion=None, candidate_causes=None) -> IntegratedAnalysisReport:
    return IntegratedAnalysisReport(
        session_id="s1",
        dispersion=dispersion,
        frequent_segments=FrequentSegmentStats(
            n=24,
            segment_counts={"20": 24},
            ring_counts={},
            horizontal_streaks=DirectionStreaks(axis="horizontal", max_streak=1, streak_lengths=[]),
            vertical_streaks=DirectionStreaks(axis="vertical", max_streak=1, streak_lengths=[]),
        ),
        late_round=LateRoundComparison(
            early_rounds=[1, 2, 3, 4],
            late_rounds=[5, 6, 7, 8],
            early_score_average=20.0,
            late_score_average=10.0,
            score_delta=-10.0,
            early_dispersion=None,
            late_dispersion=None,
            insufficient_data=False,
        ),
        form_correlations=[],
        candidate_causes=candidate_causes or [],
    )


def test_observations_present_even_with_no_dispersion():
    report = _minimal_report()
    output = build_advisor_output(report)
    assert len(output.observations) >= 1
    assert any("座標データが無い" in o.description for o in output.observations)


def test_observations_include_dispersion_stats_when_present():
    dispersion = compute_grouping_stats([(0.1, 0.1)] * 24)
    report = _minimal_report(dispersion=dispersion)
    output = build_advisor_output(report)
    assert any("BULL率" in o.description for o in output.observations)


def test_no_candidate_causes_means_no_hypotheses_and_extra_caveat():
    report = _minimal_report()
    output = build_advisor_output(report)
    assert output.hypotheses == []
    assert output.recommended_tests == []
    assert any("原因候補が無い" in c.text for c in output.caveats)


def test_candidate_cause_produces_matching_hypothesis_and_recommended_test():
    cause = CandidateCause(
        category="肘/前腕角度",
        description="test description",
        supporting_evidence=["pearson_r=0.8"],
        confidence=0.4,
        outcome_metric_name="mean_center_distance",
    )
    report = _minimal_report(candidate_causes=[cause])
    output = build_advisor_output(report)
    assert len(output.hypotheses) == 1
    assert output.hypotheses[0].category == "肘/前腕角度"
    assert output.hypotheses[0].confidence == pytest.approx(0.4)
    assert len(output.recommended_tests) == 1
    assert output.recommended_tests[0].confidence == pytest.approx(0.4)
    assert "compare_baseline_vs_test" in output.recommended_tests[0].measurement_plan


def test_evidence_and_expected_effect_propagate_from_candidate_cause():
    """docs §8: each piece of advice should carry evidence + an expected
    effect, as far as possible — verify these survive the
    CandidateCause -> Hypothesis/RecommendedTest translation rather than
    being silently dropped."""
    cause = CandidateCause(
        category="肘/前腕角度",
        description="test description",
        supporting_evidence=["pearson_r=0.62", "n=40"],
        confidence=0.45,
        outcome_metric_name="mean_center_distance",
    )
    report = _minimal_report(candidate_causes=[cause])
    output = build_advisor_output(report)

    assert output.hypotheses[0].evidence == ["pearson_r=0.62", "n=40"]
    test = output.recommended_tests[0]
    assert test.evidence == ["pearson_r=0.62", "n=40"]
    assert "mean_center_distance" in test.expected_effect
    # The expected effect must stay hedged, never a promise of improvement.
    assert "保証するものではない" in test.expected_effect


def test_experiment_history_is_summarized_in_observations():
    history = [
        Experiment(intervention_id="iv1", baseline_session_ids=["s1"], decision=Decision.CONTINUE),
        Experiment(intervention_id="iv2", baseline_session_ids=["s2"], decision=Decision.RETEST),
        Experiment(intervention_id="iv3", baseline_session_ids=["s3"], decision=None),  # not yet decided
    ]
    report = _minimal_report()
    output = build_advisor_output(report, experiment_history=history)
    assert any("過去の改善実験2件" in o.description for o in output.observations)


def test_empty_experiment_history_adds_no_observation():
    report = _minimal_report()
    without = build_advisor_output(report)
    with_empty = build_advisor_output(report, experiment_history=[])
    assert len(without.observations) == len(with_empty.observations)


def test_standard_caveats_always_present():
    report = _minimal_report()
    output = build_advisor_output(report)
    assert len(output.caveats) >= 3


def test_never_generates_a_banned_absolute_phrase():
    """Regression guard for AGENTS.md §2: 'AIに原因を断定させない。「絶対に
    これが原因」という表現は禁止.' — scan every piece of generated text."""
    cause = CandidateCause(
        category="肘/前腕角度", description="test", supporting_evidence=[], confidence=0.5
    )
    report = _minimal_report(candidate_causes=[cause])
    output = build_advisor_output(report, experiment_history=[
        Experiment(intervention_id="iv1", baseline_session_ids=["s1"], decision=Decision.CONTINUE)
    ])
    all_text = " ".join(
        [o.description for o in output.observations]
        + [h.description for h in output.hypotheses]
        + [
            t.description + t.measurement_plan + t.decision_criteria + t.expected_effect
            for t in output.recommended_tests
        ]
        + [c.text for c in output.caveats]
    )
    for phrase in BANNED_ABSOLUTE_PHRASES:
        assert phrase not in all_text


def test_hypotheses_are_tagged_advice_not_measured():
    cause = CandidateCause(category="グリップ", description="d", supporting_evidence=[], confidence=0.3)
    report = _minimal_report(candidate_causes=[cause])
    output = build_advisor_output(report)
    assert output.hypotheses[0].data_kind is DataKind.ADVICE
    assert output.observations[0].data_kind is DataKind.CALCULATED


def test_output_is_json_serializable():
    import json

    cause = CandidateCause(category="グリップ", description="d", supporting_evidence=[], confidence=0.3)
    report = _minimal_report(candidate_causes=[cause])
    output = build_advisor_output(report)
    json.dumps(output.to_dict(), ensure_ascii=False)


def test_session_id_matches_report():
    report = _minimal_report()
    output = build_advisor_output(report)
    assert output.session_id == "s1"
