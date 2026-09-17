"""Candidate-cause generation (docs §16 原因推定のルール).

docs §16, verbatim: "「着弾が下だから、必ずリリースが低い」とは断定しない。
原因候補を [...] に分類し、各特徴量と着弾傾向の一致度から仮説を生成する。"

This module NEVER asserts a single definitive cause (AGENTS.md §2:
"AIに原因を断定させない"). It only turns an already-computed
FormCorrelation (dartsanalytics.integrated.correlation — itself already
refusing to report anything from too little data) into a labeled
candidate when the correlation is strong enough to be worth surfacing.
"一致度" (degree of agreement) in the spec maps naturally to |pearson_r|
here — no candidate is generated for a feature with only a weak
correlation, and an empty list (no candidates at all) is a valid, honest
result, not a failure.

Cause categories are exactly the 9 named in docs §16:
リリース位置 / 肘・前腕角度 / 手首の動き / 頭部・体幹移動 / 足位置 /
肩の開き / 狙い線 / グリップ / 用具.

Only the categories with a feature already computed somewhere in this
codebase (Phase 5 pose features, Phase 6 grip features) are wired up
here — see FEATURE_CATEGORY_MAP. The rest are intentionally left
unimplemented rather than guessed at:

- リリース位置 (release position): needs a calibrated release-point ->
  board-impact mapping; not built in any phase yet (pose.release only
  finds a release-candidate *timestamp*, not a calibrated spatial
  position).
- 足位置 (foot position): needs analysis of video angle D (遠景) /
  standing-position tracking; not implemented (Phase 4 only covers video
  intake/quality, not a foot-position feature extractor).
- 狙い線 (aim line): needs declared_target vs actual_target gap analysis
  across enough throws to be meaningful; not implemented.
- 用具 (equipment): equipment-change-vs-outcome comparison is Phase 8's
  Baseline/Intervention/Test job (docs §20), not a static per-session
  candidate-cause heuristic — computing it here would duplicate Phase 8's
  purpose with a weaker, unpaired method.
- 手首の動き (wrist motion, from pose): pose.release only tracks wrist
  *speed*, not a directional deviation that could plausibly explain a
  directional board bias — there is no directional evidence to correlate
  yet.
"""

from __future__ import annotations

from dataclasses import dataclass

from dartsanalytics.common.enums import DataKind
from dartsanalytics.integrated.correlation import FormCorrelation

MAX_CAUSE_CONFIDENCE = 0.6

# |pearson_r| below this is not proposed as a candidate cause — a
# documented convention about not overclaiming weak effects, not a
# formal statistical-significance test (see correlation.py for the
# separate small-n guard).
CORRELATION_THRESHOLD_FOR_CANDIDATE = 0.5

FEATURE_CATEGORY_MAP: dict[str, str] = {
    # Phase 5 pose features
    "body_tilt_deg": "頭部/体幹移動",
    "shoulder_tilt_deg": "肩の開き",
    "hip_tilt_deg": "肩の開き",  # hip-line tilt also reflects body opening;
    # grouped under the same docs §16 category rather than inventing a
    # 10th category the spec doesn't list.
    "left_elbow_angle_deg": "肘/前腕角度",
    "right_elbow_angle_deg": "肘/前腕角度",
    # Phase 6 grip features
    "wrist_angle_deg": "グリップ",  # grip module's 2D hand-orientation angle
    # (from the grip photo, not the throwing-motion video) — grouped under
    # グリップ since it's a grip-photo-derived feature.
    "barrel_axis_deg": "グリップ",
    "thumb_curl_angle_deg": "グリップ",
    "index_curl_angle_deg": "グリップ",
    "middle_curl_angle_deg": "グリップ",
}


@dataclass(frozen=True)
class CandidateCause:
    category: str
    description: str
    supporting_evidence: list[str]
    confidence: float
    data_kind: DataKind = DataKind.ADVICE

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "description": self.description,
            "supporting_evidence": self.supporting_evidence,
            "confidence": self.confidence,
            "data_kind": self.data_kind.value,
        }


def generate_candidate_causes(correlations: list[FormCorrelation]) -> list[CandidateCause]:
    causes: list[CandidateCause] = []
    for corr in correlations:
        category = FEATURE_CATEGORY_MAP.get(corr.form_feature_name)
        if category is None:
            continue  # unmapped feature name -> no category to attribute it to; skip rather than guess
        if abs(corr.pearson_r) < CORRELATION_THRESHOLD_FOR_CANDIDATE:
            continue

        confidence = min(MAX_CAUSE_CONFIDENCE, corr.confidence * abs(corr.pearson_r))
        causes.append(
            CandidateCause(
                category=category,
                description=(
                    f"{corr.form_feature_name}と{corr.outcome_metric_name}の間に"
                    f"相関候補を検出（r={corr.pearson_r:.2f}, n={corr.n}）。"
                    "これは候補であり、原因と断定するものではない。"
                ),
                supporting_evidence=[f"pearson_r={corr.pearson_r:.3f}", f"n={corr.n}"],
                confidence=confidence,
            )
        )
    return causes
