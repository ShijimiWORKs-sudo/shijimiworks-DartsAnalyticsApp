"""Local AI Advisor (docs §19 AIアドバイザー; 非機能要件 §25
「外部AI APIは必須にしない」).

docs §19, verbatim inputs: "統計値, ボード座標特徴量, フォーム特徴量,
グリップ特徴量, 用具情報, 過去の改善履歴, 信頼度". "AIには生動画そのもの
を丸投げして結論を出させず、抽出済み特徴量と必要な画像フレームを渡す。"

This module is a deterministic, template-based advisor — NOT a call to an
external LLM/AI API. That's a deliberate reading of §25's "外部AI APIは
必須にしない" (an external AI API must never be a *hard requirement*):
everything here runs fully offline from already-computed,
already-confidence-scored inputs (Phase 3/7/8 outputs — statistics,
board features, and via Phase 7's candidate_causes, the form/grip
features too), so the app works end-to-end with zero network dependency.
A real LLM-backed advisor could be layered on top of this later (e.g. to
turn these structured observations/hypotheses into more natural prose),
but the separation-of-concerns job itself (AGENTS.md §2: "AIに原因を
断定させない。「絶対にこれが原因」という表現は禁止") has to hold
regardless of whether an LLM is involved, so it's enforced here as the
baseline: everything generated is checked against BANNED_ABSOLUTE_PHRASES
in tests.

過去の改善履歴 (docs §19) comes in as `experiment_history` — a list of
dartsanalytics.experiments.models.Experiment (Phase 8) — and is folded
into the observations, not silently ignored.
"""

from __future__ import annotations

from dartsanalytics.advisor.models import AdvisorOutput, Caveat, Hypothesis, Observation, RecommendedTest
from dartsanalytics.experiments.models import Experiment
from dartsanalytics.integrated.causes import CandidateCause
from dartsanalytics.integrated.report import IntegratedAnalysisReport

STANDARD_CAVEATS: tuple[str, ...] = (
    "これらは推定・仮説であり、断定的な原因ではない。",
    "映像・グリップ写真から抽出した特徴量は実データでの検証がまだ済んでいない場合がある"
    "（docs/codex/reports/phase5_notes.md, phase6_notes.md 参照）。",
    "提案された変更は一度に1項目のみ試し、Baseline/Testで効果を比較すること（docs §18/§20）。",
)

NO_CANDIDATE_CAUSES_CAVEAT = "現時点では十分な根拠を持つ原因候補が無いため、仮説・推奨テストは生成していない。"

# Regression guard (see module docstring + tests/test_advisor.py): nothing
# this module generates may ever contain one of these — that would be
# exactly the "断定" (definitive assertion) the project's rules forbid.
BANNED_ABSOLUTE_PHRASES: tuple[str, ...] = (
    "絶対に",
    "必ずこれが原因",
    "間違いなく原因",
    "確定的な原因",
)


def _observations_from_report(report: IntegratedAnalysisReport) -> list[Observation]:
    observations: list[Observation] = []

    if report.dispersion:
        d = report.dispersion
        observations.append(
            Observation(
                f"平均中心距離={d.mean_center_distance:.4f}, BULL率={d.bull_rate:.2f}, "
                f"上下偏り={d.vertical_bias:+.4f}, 左右偏り={d.horizontal_bias:+.4f}（n={d.n}）"
            )
        )
    else:
        observations.append(Observation("座標データが無いため、着弾分布（散らばり・偏り）は評価できない。"))

    if report.late_round.insufficient_data:
        observations.append(Observation("ラウンド数が少なく、ラウンド前半/後半の比較はできない。"))
    else:
        lr = report.late_round
        if lr.early_score_average is not None and lr.late_score_average is not None:
            observations.append(
                Observation(
                    f"前半（ラウンド{lr.early_rounds}）平均{lr.early_score_average:.2f}点/投 → "
                    f"後半（ラウンド{lr.late_rounds}）平均{lr.late_score_average:.2f}点/投"
                    f"（差分{lr.score_delta:+.2f}）"
                )
            )

    if report.frequent_segments:
        fs = report.frequent_segments
        if fs.horizontal_streaks.max_streak >= 3:
            observations.append(Observation(f"左右いずれか同方向への連続{fs.horizontal_streaks.max_streak}投の偏りを検出。"))
        if fs.vertical_streaks.max_streak >= 3:
            observations.append(Observation(f"上下いずれか同方向への連続{fs.vertical_streaks.max_streak}投の偏りを検出。"))

    return observations


def _observations_from_experiment_history(experiment_history: list[Experiment] | None) -> list[Observation]:
    if not experiment_history:
        return []
    decided = [e for e in experiment_history if e.decision is not None]
    if not decided:
        return []
    counts: dict[str, int] = {}
    for e in decided:
        counts[e.decision.value] = counts.get(e.decision.value, 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    return [Observation(f"過去の改善実験{len(decided)}件の内訳: {summary}")]


def _hypotheses_from_causes(candidate_causes: list[CandidateCause]) -> list[Hypothesis]:
    return [
        Hypothesis(category=c.category, description=c.description, confidence=c.confidence)
        for c in candidate_causes
    ]


def _recommended_tests_from_causes(candidate_causes: list[CandidateCause]) -> list[RecommendedTest]:
    return [
        RecommendedTest(
            related_category=c.category,
            description=(
                f"「{c.category}」に関連する変更を1つ選び、30〜60投のTestセッションを実施する"
                "（docs §18: 変更は一度に1項目のみ）。"
            ),
            measurement_plan=(
                "dartsanalytics.experiments.compare_baseline_vs_test で現在までのセッション群を"
                "Baseline、変更後のセッション群をTestとして比較する。"
            ),
            decision_criteria="dartsanalytics.experiments.decide の結果（continue/revert/retest）を判定基準とする。",
            confidence=c.confidence,
        )
        for c in candidate_causes
    ]


def build_advisor_output(
    report: IntegratedAnalysisReport,
    *,
    experiment_history: list[Experiment] | None = None,
) -> AdvisorOutput:
    observations = _observations_from_report(report) + _observations_from_experiment_history(experiment_history)
    hypotheses = _hypotheses_from_causes(report.candidate_causes)
    recommended_tests = _recommended_tests_from_causes(report.candidate_causes)

    caveats = [Caveat(text=t) for t in STANDARD_CAVEATS]
    if not report.candidate_causes:
        caveats.append(Caveat(text=NO_CANDIDATE_CAUSES_CAVEAT))

    return AdvisorOutput(
        session_id=report.session_id,
        observations=observations,
        hypotheses=hypotheses,
        recommended_tests=recommended_tests,
        caveats=caveats,
    )
