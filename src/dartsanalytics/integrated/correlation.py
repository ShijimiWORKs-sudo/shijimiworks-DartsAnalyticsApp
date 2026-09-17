"""Form-feature <-> throw-result correlation (docs §Phase7 'form
correlations').

docs §14 explicitly does not assume a single throw can always be linked
1:1 to a specific video frame/pose sample (4 videos are not
time-synchronized; a throw only gets a `throw_group_id` link to a
specific form-feature sample when tracking actually succeeded — see
dartsanalytics.pose.analysis and docs §14 "4動画の統合方法"). Pretending a
false per-throw pairing exists would fabricate precision the data doesn't
have.

So this module correlates *session-level* aggregates instead — e.g. one
session's average body_tilt_deg vs that same session's dispersion/bias —
across multiple sessions. The caller (a future orchestration layer, or
Phase 9's AI advisor) is responsible for building the paired-samples list
from its own session history; this module only does the correlation math
and the associated confidence framing, and refuses to compute anything
meaningful-looking from too few samples.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from dartsanalytics.common.enums import DataKind

# A Pearson r computed on fewer than this many paired sessions is not
# reported at all — at small n, r is easy to push toward +-1 by chance
# alone, which would misrepresent noise as a "correlation candidate"
# (解析不能なものを無理に判定しない). Documented, overridable convention,
# not a formal statistical power calculation.
MIN_SAMPLES_FOR_CORRELATION = 5

MAX_CORRELATION_CONFIDENCE = 0.7


@dataclass(frozen=True)
class FormCorrelation:
    form_feature_name: str
    outcome_metric_name: str
    n: int
    pearson_r: float
    confidence: float
    data_kind: DataKind = DataKind.ESTIMATED

    def to_dict(self) -> dict:
        return {
            "form_feature_name": self.form_feature_name,
            "outcome_metric_name": self.outcome_metric_name,
            "n": self.n,
            "pearson_r": self.pearson_r,
            "confidence": self.confidence,
            "data_kind": self.data_kind.value,
        }


def compute_form_correlation(
    form_feature_name: str,
    outcome_metric_name: str,
    paired_samples: list[tuple[float, float]],
) -> FormCorrelation | None:
    """`paired_samples`: one (form_feature_value, outcome_metric_value) pair
    per session. Returns None (not a fabricated 0.0) when there isn't
    enough data or the data has no variance to correlate."""
    n = len(paired_samples)
    if n < MIN_SAMPLES_FOR_CORRELATION:
        return None

    xs = [p[0] for p in paired_samples]
    ys = [p[1] for p in paired_samples]
    if len(set(xs)) < 2 or len(set(ys)) < 2:
        return None  # zero variance on one side -> correlation is undefined, not zero

    r = float(np.corrcoef(xs, ys)[0, 1])
    if math.isnan(r):
        return None

    # Confidence scales with sample size (more paired sessions = more
    # trustworthy), capped well below "high confidence" — correlation
    # strength alone never implies causal certainty (that's the more
    # conservative, separate step in dartsanalytics.integrated.causes).
    confidence = min(MAX_CORRELATION_CONFIDENCE, 0.2 + 0.05 * n)

    return FormCorrelation(
        form_feature_name=form_feature_name,
        outcome_metric_name=outcome_metric_name,
        n=n,
        pearson_r=r,
        confidence=confidence,
    )
