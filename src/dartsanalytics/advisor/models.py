"""Local AI Advisor output shapes (docs §19).

docs §19, verbatim: "AI出力は、観測/推定/提案/注意点を分離する。" These
four dataclasses are exactly that separation — kept as distinct types
(not four fields on one blob of text) so nothing downstream can
accidentally blend a factual observation with a hedged hypothesis.
"""

from __future__ import annotations

from dataclasses import dataclass

from dartsanalytics.common.enums import DataKind


@dataclass(frozen=True)
class Observation:
    """A factual, deterministic statement about already-computed stats —
    no inference, no confidence needed (DataKind.CALCULATED, same as
    dartsanalytics.integrated.report's dispersion/frequent_segments/
    late_round outputs it's built from)."""

    description: str
    data_kind: DataKind = DataKind.CALCULATED

    def to_dict(self) -> dict:
        return {"description": self.description, "data_kind": self.data_kind.value}


@dataclass(frozen=True)
class Hypothesis:
    """A candidate explanation — never a definitive cause (AGENTS.md §2:
    "AIに原因を断定させない"). Wraps dartsanalytics.integrated.causes.
    CandidateCause with the same confidence, unmodified."""

    category: str
    description: str
    confidence: float
    data_kind: DataKind = DataKind.ADVICE

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "description": self.description,
            "confidence": self.confidence,
            "data_kind": self.data_kind.value,
        }


@dataclass(frozen=True)
class RecommendedTest:
    """docs §17's improvement-proposal shape, narrowed to the part this
    module can respond for: "今回試す変更 / 測定方法 / 変更後の判定基準".
    Always points at dartsanalytics.experiments (Phase 8) for the actual
    measurement/decision machinery rather than inventing its own — one
    verification path, not two."""

    related_category: str
    description: str
    measurement_plan: str
    decision_criteria: str
    confidence: float
    data_kind: DataKind = DataKind.ADVICE

    def to_dict(self) -> dict:
        return {
            "related_category": self.related_category,
            "description": self.description,
            "measurement_plan": self.measurement_plan,
            "decision_criteria": self.decision_criteria,
            "confidence": self.confidence,
            "data_kind": self.data_kind.value,
        }


@dataclass(frozen=True)
class Caveat:
    text: str

    def to_dict(self) -> dict:
        return {"text": self.text}


@dataclass(frozen=True)
class AdvisorOutput:
    session_id: str
    observations: list[Observation]
    hypotheses: list[Hypothesis]
    recommended_tests: list[RecommendedTest]
    caveats: list[Caveat]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "observations": [o.to_dict() for o in self.observations],
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "recommended_tests": [t.to_dict() for t in self.recommended_tests],
            "caveats": [c.to_dict() for c in self.caveats],
        }
