"""Ties dartsanalytics.integrated's pieces into one per-session report
(docs §Phase7: dispersion / directional bias / frequent segments /
late-round degradation / form correlations / candidate causes).

Dispersion + directional bias reuse dartsanalytics.board.grouping
directly (GroupingStats already has both — see frequent_segments.py
docstring for why they aren't recomputed here).

form_correlations cannot be computed from a single session (see
correlation.py — it needs paired samples across multiple sessions), so
the caller passes in whatever correlations it has already computed
(e.g. from a multi-session history); an empty/omitted list is valid and
simply yields no candidate_causes either (causes.py only generates from
correlations that were actually supplied).

Matches docs §21's `analysis_reports` table (report_json, already present
in the Phase 0 schema — no migration needed here, same pattern as Phase 6
reusing the pre-existing grip_analysis_runs table).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dartsanalytics.board.grouping import GroupingStats, compute_grouping_stats
from dartsanalytics.integrated.causes import CandidateCause, generate_candidate_causes
from dartsanalytics.integrated.correlation import FormCorrelation
from dartsanalytics.integrated.frequent_segments import FrequentSegmentStats, compute_frequent_segment_stats
from dartsanalytics.integrated.late_round import LateRoundComparison, compare_early_vs_late_rounds
from dartsanalytics.models.entities import PracticeSession


@dataclass(frozen=True)
class IntegratedAnalysisReport:
    session_id: str
    dispersion: GroupingStats | None
    frequent_segments: FrequentSegmentStats | None
    late_round: LateRoundComparison
    form_correlations: list[FormCorrelation] = field(default_factory=list)
    candidate_causes: list[CandidateCause] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "dispersion": self.dispersion.to_dict() if self.dispersion else None,
            "frequent_segments": self.frequent_segments.to_dict() if self.frequent_segments else None,
            "late_round": self.late_round.to_dict(),
            "form_correlations": [c.to_dict() for c in self.form_correlations],
            "candidate_causes": [c.to_dict() for c in self.candidate_causes],
        }


def build_integrated_report(
    session: PracticeSession,
    *,
    form_correlations: list[FormCorrelation] | None = None,
) -> IntegratedAnalysisReport:
    if not session.throws:
        raise ValueError("build_integrated_report requires a session with at least one throw")

    points = [
        (t.normalized_x, t.normalized_y)
        for t in session.throws
        if t.normalized_x is not None and t.normalized_y is not None
    ]
    dispersion = compute_grouping_stats(points) if points else None
    frequent_segments = compute_frequent_segment_stats(session.throws)
    late_round = compare_early_vs_late_rounds(session)
    correlations = list(form_correlations) if form_correlations else []
    candidate_causes = generate_candidate_causes(correlations)

    return IntegratedAnalysisReport(
        session_id=session.session_id,
        dispersion=dispersion,
        frequent_segments=frequent_segments,
        late_round=late_round,
        form_correlations=correlations,
        candidate_causes=candidate_causes,
    )
