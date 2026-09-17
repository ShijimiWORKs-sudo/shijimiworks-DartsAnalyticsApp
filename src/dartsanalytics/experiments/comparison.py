"""Baseline vs Test metric comparison (docs §20 改善効果検証).

docs §20:
```
Baseline 30～60投
↓
変更1項目
↓
Test 30～60投
↓
比較
↓
継続 / 中止 / 再試験
```

比較指標(docs §20, verbatim): BULL率 / BULL周辺集中率 / 平均中心距離 /
X/Y偏差 / X/Y標準偏差 / 95%半径 / COUNT-UP平均 / ラウンド後半の崩れ

Reuses existing modules rather than recomputing: dispersion-shaped
metrics come from dartsanalytics.board.grouping (Phase 3), COUNT-UP平均
from dartsanalytics.countup.session_result (Phase 1), and ラウンド後半の
崩れ from dartsanalytics.integrated.late_round (Phase 7).

"Baseline/Test 30〜60投" doesn't require a single session — a baseline or
test set can be one or more sessions pooled together to reach that throw
count, which is why every function here takes a *list* of sessions.
"""

from __future__ import annotations

from dataclasses import dataclass

from dartsanalytics.board.grouping import compute_grouping_stats
from dartsanalytics.countup.session_result import summarize
from dartsanalytics.integrated.late_round import compare_early_vs_late_rounds
from dartsanalytics.models.entities import PracticeSession

# docs §20: "Baseline 30～60投" / "Test 30～60投" — a group with fewer
# throws than this is not compared with confidence (see decision.py,
# which returns RETEST rather than a snap judgment when this isn't met).
MIN_THROWS_PER_GROUP = 30

# True = higher is better for that metric, False = lower is better.
# Documented convention (docs §20 doesn't rank/weight the 8 metrics, so
# this module treats them as independent facts — see decision.py for how
# they're combined into one Decision).
METRIC_DIRECTIONS: dict[str, bool] = {
    "bull_rate": True,
    "bull_vicinity_rate": True,
    "mean_center_distance": False,
    "std_x": False,
    "std_y": False,
    "p95_radius": False,
    "countup_average": True,
    "late_round_score_delta": True,  # closer to 0 (or positive) = late rounds held up better
}


@dataclass(frozen=True)
class ExperimentMetricResult:
    metric_name: str
    baseline_value: float | None
    test_value: float | None
    delta: float | None  # test - baseline; None if either side is unavailable
    higher_is_better: bool

    def to_dict(self) -> dict:
        return {
            "metric_name": self.metric_name,
            "baseline_value": self.baseline_value,
            "test_value": self.test_value,
            "delta": self.delta,
            "higher_is_better": self.higher_is_better,
        }


@dataclass(frozen=True)
class ExperimentComparison:
    baseline_throw_count: int
    test_throw_count: int
    metrics: list[ExperimentMetricResult]

    def to_dict(self) -> dict:
        return {
            "baseline_throw_count": self.baseline_throw_count,
            "test_throw_count": self.test_throw_count,
            "metrics": [m.to_dict() for m in self.metrics],
        }


def _pooled_points(sessions: list[PracticeSession]) -> list[tuple[float, float]]:
    return [
        (t.normalized_x, t.normalized_y)
        for s in sessions
        for t in s.throws
        if t.normalized_x is not None and t.normalized_y is not None
    ]


def _pooled_throw_count(sessions: list[PracticeSession]) -> int:
    return sum(len(s.throws) for s in sessions)


def _weighted_countup_average(sessions: list[PracticeSession]) -> float | None:
    total_score = 0
    total_throws = 0
    for s in sessions:
        result = summarize(s)
        total_score += result.total_score
        total_throws += result.throw_count
    return (total_score / total_throws) if total_throws else None


def _average_late_round_score_delta(sessions: list[PracticeSession]) -> float | None:
    deltas = [
        cmp.score_delta
        for s in sessions
        for cmp in [compare_early_vs_late_rounds(s)]
        if not cmp.insufficient_data and cmp.score_delta is not None
    ]
    return (sum(deltas) / len(deltas)) if deltas else None


def _group_metrics(sessions: list[PracticeSession]) -> dict[str, float | None]:
    points = _pooled_points(sessions)
    dispersion = compute_grouping_stats(points) if points else None
    return {
        "bull_rate": dispersion.bull_rate if dispersion else None,
        "bull_vicinity_rate": dispersion.bull_vicinity_rate if dispersion else None,
        "mean_center_distance": dispersion.mean_center_distance if dispersion else None,
        "std_x": dispersion.std_x if dispersion else None,
        "std_y": dispersion.std_y if dispersion else None,
        "p95_radius": dispersion.percentile_radii["p95"] if dispersion else None,
        "countup_average": _weighted_countup_average(sessions),
        "late_round_score_delta": _average_late_round_score_delta(sessions),
    }


def compare_baseline_vs_test(
    baseline_sessions: list[PracticeSession], test_sessions: list[PracticeSession]
) -> ExperimentComparison:
    if not baseline_sessions or not test_sessions:
        raise ValueError("both baseline_sessions and test_sessions must be non-empty")

    baseline_metrics = _group_metrics(baseline_sessions)
    test_metrics = _group_metrics(test_sessions)

    results = []
    for name, higher_is_better in METRIC_DIRECTIONS.items():
        bv = baseline_metrics[name]
        tv = test_metrics[name]
        delta = (tv - bv) if (bv is not None and tv is not None) else None
        results.append(
            ExperimentMetricResult(
                metric_name=name, baseline_value=bv, test_value=tv, delta=delta, higher_is_better=higher_is_better
            )
        )

    return ExperimentComparison(
        baseline_throw_count=_pooled_throw_count(baseline_sessions),
        test_throw_count=_pooled_throw_count(test_sessions),
        metrics=results,
    )
