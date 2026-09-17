"""Tests for contract/support_app_assessment.py (§11統合方針4「DartsSupportApp
のOpenAI API連携拡張ポイントを使う」の、DartsAnalyticsApp側エクスポート実装)。
"""

from __future__ import annotations

import json

import pytest

from dartsanalytics.advisor.generate import build_advisor_output
from dartsanalytics.board.grouping import compute_grouping_stats
from dartsanalytics.common.enums import DataKind
from dartsanalytics.contract.support_app_assessment import (
    ASSESSMENT_HEADING_MAP,
    CANNOT_JUDGE_FROM_VIDEO,
    NOT_REGISTERED,
    PARSE_STATUS_PARSED,
    PROPOSED_SOURCE_TYPE,
    _hash_assessment_raw_text,
    build_support_app_assessment_draft,
)
from dartsanalytics.integrated.causes import CandidateCause
from dartsanalytics.integrated.frequent_segments import DirectionStreaks, FrequentSegmentStats
from dartsanalytics.integrated.late_round import LateRoundComparison
from dartsanalytics.integrated.report import IntegratedAnalysisReport


def _late_round() -> LateRoundComparison:
    return LateRoundComparison(
        early_rounds=[1, 2, 3, 4],
        late_rounds=[5, 6, 7, 8],
        early_score_average=20.0,
        late_score_average=10.0,
        score_delta=-10.0,
        early_dispersion=None,
        late_dispersion=None,
        insufficient_data=False,
    )


def _report(*, dispersion=None, candidate_causes=None) -> IntegratedAnalysisReport:
    return IntegratedAnalysisReport(
        session_id="s1",
        dispersion=dispersion,
        frequent_segments=FrequentSegmentStats(
            n=24,
            segment_counts={"20": 10, "T20": 8, "5": 6},
            ring_counts={},
            horizontal_streaks=DirectionStreaks(axis="horizontal", max_streak=1, streak_lengths=[]),
            vertical_streaks=DirectionStreaks(axis="vertical", max_streak=1, streak_lengths=[]),
        ),
        late_round=_late_round(),
        form_correlations=[],
        candidate_causes=candidate_causes or [],
    )


def _candidate_cause(confidence: float = 0.6) -> CandidateCause:
    return CandidateCause(
        category="グリップ",
        description="グリップ圧の変化とスコア低下に相関がみられる（因果は未確定）。",
        confidence=confidence,
        data_kind=DataKind.ADVICE,
        supporting_evidence=["pearson_r=-0.55 (n=20)"],
        outcome_metric_name="score",
    )


def test_all_15_headings_present_in_raw_text():
    report = _report()
    advisor_output = build_advisor_output(report)
    draft = build_support_app_assessment_draft(report, advisor_output)

    for heading in ASSESSMENT_HEADING_MAP.values():
        assert f"【{heading}】" in draft.raw_text
    assert draft.recognized_heading_count == len(ASSESSMENT_HEADING_MAP)
    assert draft.parse_status == PARSE_STATUS_PARSED


def test_parsed_json_keys_match_heading_map_keys():
    report = _report()
    advisor_output = build_advisor_output(report)
    draft = build_support_app_assessment_draft(report, advisor_output)

    assert set(draft.parsed_json.keys()) == set(ASSESSMENT_HEADING_MAP.keys())
    # Every value must be JSON-serializable text (this would become the
    # ai_form_assessments.parsed_json TEXT column on the DartsSupportApp side).
    json.dumps(draft.parsed_json, ensure_ascii=False)


def test_pose_related_headings_say_cannot_judge_from_video_when_unwired():
    # Phase 5 pose features aren't wired into IntegratedAnalysisReport yet
    # (release-readiness.md 未解決事項8) — these headings must honestly say
    # so using DartsSupportApp's OWN existing convention, not silently omit
    # or invent plausible-sounding content.
    report = _report()
    advisor_output = build_advisor_output(report)
    draft = build_support_app_assessment_draft(report, advisor_output)

    for key in ("stance", "setup", "takeback", "release", "followThrough", "headShoulderElbow"):
        assert draft.parsed_json[key] == CANNOT_JUDGE_FROM_VIDEO


def test_no_candidate_causes_yields_not_registered_improvement_points():
    report = _report(candidate_causes=[])
    advisor_output = build_advisor_output(report)
    draft = build_support_app_assessment_draft(report, advisor_output)

    assert draft.parsed_json["improvementPoints"] == NOT_REGISTERED
    assert draft.parsed_json["nextPriority"] == NOT_REGISTERED


def test_candidate_cause_hypothesis_never_asserts_causation():
    report = _report(candidate_causes=[_candidate_cause()])
    advisor_output = build_advisor_output(report)
    draft = build_support_app_assessment_draft(report, advisor_output)

    banned = ["原因である", "確定した", "証明された", "間違いなく"]
    for phrase in banned:
        assert phrase not in draft.parsed_json["improvementPoints"]
        assert phrase not in draft.raw_text


def test_next_priority_capped_at_two_items():
    causes = [_candidate_cause(confidence=c) for c in (0.6, 0.55, 0.51)]
    report = _report(candidate_causes=causes)
    advisor_output = build_advisor_output(report)
    draft = build_support_app_assessment_draft(report, advisor_output)

    # Three candidate causes -> three recommended tests, but nextPriority
    # must cap at MAX_NEXT_PRIORITY_ITEMS (2), matching DartsSupportApp's
    # own prompt convention ("最大2点に絞ってください").
    assert len(advisor_output.recommended_tests) == 3
    assert draft.parsed_json["nextPriority"].count("・グリップ：") == 2


def test_raw_hash_matches_manual_fnv1a_computation():
    report = _report()
    advisor_output = build_advisor_output(report)
    draft = build_support_app_assessment_draft(report, advisor_output)

    assert draft.raw_hash == _hash_assessment_raw_text(draft.raw_text)
    assert len(draft.raw_hash) == 8
    int(draft.raw_hash, 16)  # must be valid lowercase hex


def test_raw_hash_is_deterministic_and_sensitive_to_content():
    report_a = _report()
    report_b = _report(dispersion=compute_grouping_stats([(0.1, 0.1)] * 24))
    advisor_output_a = build_advisor_output(report_a)
    advisor_output_b = build_advisor_output(report_b)

    draft_a1 = build_support_app_assessment_draft(report_a, advisor_output_a)
    draft_a2 = build_support_app_assessment_draft(report_a, advisor_output_a)
    draft_b = build_support_app_assessment_draft(report_b, advisor_output_b)

    assert draft_a1.raw_hash == draft_a2.raw_hash
    assert draft_a1.raw_text != draft_b.raw_text
    assert draft_a1.raw_hash != draft_b.raw_hash


def test_source_type_is_proposed_value_not_yet_a_real_column():
    report = _report()
    advisor_output = build_advisor_output(report)
    draft = build_support_app_assessment_draft(report, advisor_output)

    assert draft.source_type == PROPOSED_SOURCE_TYPE == "darts_analytics_app"


def test_mismatched_session_ids_rejected():
    report = _report()
    advisor_output = build_advisor_output(report)
    mismatched = IntegratedAnalysisReport(
        session_id="other-session",
        dispersion=None,
        frequent_segments=report.frequent_segments,
        late_round=report.late_round,
        form_correlations=[],
        candidate_causes=[],
    )
    with pytest.raises(ValueError):
        build_support_app_assessment_draft(mismatched, advisor_output)


def test_external_ids_are_optional_and_passed_through_when_given():
    report = _report()
    advisor_output = build_advisor_output(report)
    draft = build_support_app_assessment_draft(
        report,
        advisor_output,
        account_id="ext-acct-1",
        player_id="ext-player-1",
        practice_session_id="ext-session-1",
    )

    assert draft.account_id == "ext-acct-1"
    assert draft.player_id == "ext-player-1"
    assert draft.practice_session_id == "ext-session-1"

    draft_no_ids = build_support_app_assessment_draft(report, advisor_output)
    assert draft_no_ids.account_id is None
    assert draft_no_ids.player_id is None
    assert draft_no_ids.practice_session_id is None


def test_improved_since_previous_and_not_improved_yet_default_to_not_registered():
    report = _report()
    advisor_output = build_advisor_output(report)
    draft = build_support_app_assessment_draft(report, advisor_output)

    assert draft.parsed_json["improvedSincePrevious"] == NOT_REGISTERED
    assert draft.parsed_json["notImprovedYet"] == NOT_REGISTERED


def test_improved_since_previous_passed_through_when_given():
    report = _report()
    advisor_output = build_advisor_output(report)
    draft = build_support_app_assessment_draft(
        report,
        advisor_output,
        improved_since_previous="前回よりグルーピングのばらつきが縮小した。",
        not_improved_yet="後半ラウンドでのスコア低下は継続。",
    )

    assert draft.parsed_json["improvedSincePrevious"] == "前回よりグルーピングのばらつきが縮小した。"
    assert draft.parsed_json["notImprovedYet"] == "後半ラウンドでのスコア低下は継続。"


def test_hash_algorithm_matches_known_fnv1a_reference_value():
    # Cross-check against a hand-computed FNV-1a value for a trivial ASCII
    # string, independent of this app's own generation logic, to catch a
    # transcription error in the ported algorithm itself.
    # FNV-1a 32-bit of "a": offset_basis=2166136261, XOR 0x61, * FNV_prime.
    h = 2166136261
    h ^= ord("a")
    h = (h * 16777619) & 0xFFFFFFFF
    expected = format(h, "08x")
    assert _hash_assessment_raw_text("a") == expected
