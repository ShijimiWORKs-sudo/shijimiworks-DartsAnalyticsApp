"""§9's "単一試行だけで因果関係を断定しない" as an enforceable check, not
just a comment.

``causal_confidence_note`` turns a trial count for one intervention into a
mandatory caution string. It never returns "confirmed" — matching
AGENTS.md §2 ("AIに原因を断定させない") and Phase 9's own
BANNED_ABSOLUTE_PHRASES policy (dartsanalytics.advisor.generate) — because
even many repeated same-player, same-equipment trials are still an
uncontrolled single-subject series, not a controlled experiment.
"""

from __future__ import annotations

from dataclasses import dataclass

from dartsanalytics.learning_log.models import LearningLogEntry

SINGLE_TRIAL_CAVEAT = (
    "この介入は今回が1回目の試行であり、単一試行の結果だけでは因果関係を"
    "断定できない。同じ変更を複数回試し、結果が再現するか確認すること。"
)
FEW_TRIALS_CAVEAT = (
    "この介入はまだ{count}回しか試行されていない。傾向が見えても、"
    "個人差・体調・疲労等の交絡要因を排除できていないため、断定的な結論は避けること。"
)
REPEATED_TRIALS_NOTE = (
    "この介入は{count}回試行されている。結果の一貫性を確認できる段階だが、"
    "それでも対照群のない単一被験者(自分自身)の記録であることに変わりはない。"
)

# Below this many trials of the SAME intervention_description, causal
# language is not warranted at all (docs §9's literal "単一試行" case, and
# the barely-more-than-single-trial case are treated the same way).
MIN_TRIALS_FOR_TREND_LANGUAGE = 3


@dataclass(frozen=True)
class InterventionHistory:
    intervention_description: str
    trial_count: int
    entries: list[LearningLogEntry]
    caution: str


def causal_confidence_note(trial_count: int) -> str:
    if trial_count <= 1:
        return SINGLE_TRIAL_CAVEAT
    if trial_count < MIN_TRIALS_FOR_TREND_LANGUAGE:
        return FEW_TRIALS_CAVEAT.format(count=trial_count)
    return REPEATED_TRIALS_NOTE.format(count=trial_count)


def summarize_intervention_history(entries: list[LearningLogEntry]) -> InterventionHistory:
    """Groups entries by intervention_description is the CALLER's job
    (repository.list_entries_by_intervention already filters to one
    description) — this just derives the trial count + caution text for
    that already-filtered list."""
    if not entries:
        raise ValueError("entries must not be empty")
    description = entries[0].intervention_description
    if any(e.intervention_description != description for e in entries):
        raise ValueError("all entries must share the same intervention_description")
    ordered = sorted(entries, key=lambda e: e.trial_number)
    trial_count = len(ordered)
    return InterventionHistory(
        intervention_description=description,
        trial_count=trial_count,
        entries=ordered,
        caution=causal_confidence_note(trial_count),
    )
