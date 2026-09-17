"""Fact-based Decision rule (docs §20: "Decisionは「継続」「戻す」「再試験」
などの事実ベースの結果にする").

This is a deterministic, rule-based classification over
ExperimentComparison — never an AI/subjective "feels better" judgment
(the same "don't let the AI assert things" spirit as
dartsanalytics.integrated.causes, applied here to the go/no-go decision
itself rather than to a cause hypothesis).

Rule: each metric's delta is judged against a fixed, documented margin
(METRIC_MARGINS — "smaller than this is noise, not a real change"); the
majority direction across all evaluated metrics decides CONTINUE/REVERT,
and anything without a clear majority (or without enough throws to trust
the comparison at all) comes back RETEST rather than forcing a call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from dartsanalytics.experiments.comparison import MIN_THROWS_PER_GROUP, ExperimentComparison

# Per-metric "this delta is noise, not a real change" threshold —
# documented convention (docs §20 doesn't specify one), not a measured
# statistical bound. Units match each metric: bull_rate/bull_vicinity_rate
# are 0-1 rates; mean_center_distance/std_x/std_y/p95_radius are
# normalized board-radius units (board radius == 1.0, so 0.02 ~= 3.4mm on
# a standard 170mm board); countup_average/late_round_score_delta are raw
# per-dart score points.
METRIC_MARGINS: dict[str, float] = {
    "bull_rate": 0.05,
    "bull_vicinity_rate": 0.05,
    "mean_center_distance": 0.02,
    "std_x": 0.02,
    "std_y": 0.02,
    "p95_radius": 0.03,
    "countup_average": 1.0,
    "late_round_score_delta": 1.0,
}


class Decision(str, Enum):
    CONTINUE = "continue"
    REVERT = "revert"
    RETEST = "retest"


@dataclass(frozen=True)
class ExperimentDecision:
    decision: Decision
    improved_count: int
    worsened_count: int
    evaluated_count: int
    reasoning: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "improved_count": self.improved_count,
            "worsened_count": self.worsened_count,
            "evaluated_count": self.evaluated_count,
            "reasoning": self.reasoning,
        }


def decide(comparison: ExperimentComparison) -> ExperimentDecision:
    if comparison.baseline_throw_count < MIN_THROWS_PER_GROUP or comparison.test_throw_count < MIN_THROWS_PER_GROUP:
        return ExperimentDecision(
            decision=Decision.RETEST,
            improved_count=0,
            worsened_count=0,
            evaluated_count=0,
            reasoning=[
                f"baseline_throw_count={comparison.baseline_throw_count}, "
                f"test_throw_count={comparison.test_throw_count} — "
                f"below the docs §20 minimum of {MIN_THROWS_PER_GROUP} throws per group; "
                "not enough data to compare with confidence."
            ],
        )

    improved = 0
    worsened = 0
    evaluated = 0
    reasoning: list[str] = []

    for m in comparison.metrics:
        if m.delta is None:
            reasoning.append(f"{m.metric_name}: no data on one or both sides — not evaluated")
            continue
        margin = METRIC_MARGINS.get(m.metric_name, 0.0)
        evaluated += 1
        signed_delta = m.delta if m.higher_is_better else -m.delta
        if signed_delta > margin:
            improved += 1
            reasoning.append(f"{m.metric_name}: improved (delta={m.delta:.4f}, margin={margin})")
        elif signed_delta < -margin:
            worsened += 1
            reasoning.append(f"{m.metric_name}: worsened (delta={m.delta:.4f}, margin={margin})")
        else:
            reasoning.append(f"{m.metric_name}: within noise margin (delta={m.delta:.4f}, margin={margin})")

    if evaluated == 0:
        return ExperimentDecision(
            decision=Decision.RETEST,
            improved_count=0,
            worsened_count=0,
            evaluated_count=0,
            reasoning=reasoning + ["no comparable metrics had data on both sides"],
        )

    if worsened > improved:
        decision = Decision.REVERT
    elif improved > worsened and improved >= (evaluated / 2):
        decision = Decision.CONTINUE
    else:
        decision = Decision.RETEST

    return ExperimentDecision(
        decision=decision,
        improved_count=improved,
        worsened_count=worsened,
        evaluated_count=evaluated,
        reasoning=reasoning,
    )
