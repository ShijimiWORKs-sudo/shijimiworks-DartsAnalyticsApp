"""Confidence bucketing and the "estimates must carry confidence" rule.

See docs/specs/DartsAnalyticsApp_詳細設計書_v1.0.md §23 and AGENTS.md §2/§3.
"""

from __future__ import annotations

from dartsanalytics.common.enums import ConfidenceLevel, DataKind


class MissingConfidenceError(ValueError):
    """Raised when an ESTIMATED or ADVICE value is created without a confidence.

    This is a hard rule (AGENTS.md §2: "すべての推定値にconfidenceを持たせる"),
    not a style preference — never suppress this by inventing a placeholder
    confidence value.
    """


def confidence_level(value: float) -> ConfidenceLevel:
    """Bucket a raw 0.0-1.0 confidence score per §23."""
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"confidence must be within [0.0, 1.0], got {value!r}")
    if value >= 0.90:
        return ConfidenceLevel.HIGH
    if value >= 0.75:
        return ConfidenceLevel.SUFFICIENT
    if value >= 0.50:
        return ConfidenceLevel.REFERENCE
    return ConfidenceLevel.PENDING


def require_confidence_for_estimate(data_kind: DataKind, confidence: float | None) -> None:
    """Enforce that ESTIMATED/ADVICE values always carry a confidence score.

    MEASURED/CALCULATED values may omit confidence (though a detection
    success rate may still be attached where available).
    """
    if data_kind in (DataKind.ESTIMATED, DataKind.ADVICE) and confidence is None:
        raise MissingConfidenceError(
            f"{data_kind.value} values must carry a confidence score "
            "(docs §9 / AGENTS.md §2 — do not defer this)."
        )
    if confidence is not None and not 0.0 <= confidence <= 1.0:
        raise ValueError(f"confidence must be within [0.0, 1.0], got {confidence!r}")
