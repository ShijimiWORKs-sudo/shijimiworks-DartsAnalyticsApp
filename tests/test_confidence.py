"""Phase 0 tests for the confidence/data-kind rules (AGENTS.md §2/§3)."""

import pytest

from dartsanalytics.common.confidence import (
    MissingConfidenceError,
    confidence_level,
    require_confidence_for_estimate,
)
from dartsanalytics.common.enums import ConfidenceLevel, DataKind


@pytest.mark.parametrize(
    "value,expected",
    [
        (1.00, ConfidenceLevel.HIGH),
        (0.90, ConfidenceLevel.HIGH),
        (0.895, ConfidenceLevel.SUFFICIENT),
        (0.75, ConfidenceLevel.SUFFICIENT),
        (0.745, ConfidenceLevel.REFERENCE),
        (0.50, ConfidenceLevel.REFERENCE),
        (0.499, ConfidenceLevel.PENDING),
        (0.00, ConfidenceLevel.PENDING),
    ],
)
def test_confidence_level_buckets(value, expected):
    assert confidence_level(value) is expected


def test_confidence_level_rejects_out_of_range():
    with pytest.raises(ValueError):
        confidence_level(1.5)
    with pytest.raises(ValueError):
        confidence_level(-0.1)


def test_estimated_without_confidence_raises():
    with pytest.raises(MissingConfidenceError):
        require_confidence_for_estimate(DataKind.ESTIMATED, None)


def test_advice_without_confidence_raises():
    with pytest.raises(MissingConfidenceError):
        require_confidence_for_estimate(DataKind.ADVICE, None)


def test_measured_without_confidence_is_allowed():
    require_confidence_for_estimate(DataKind.MEASURED, None)  # no raise


def test_calculated_without_confidence_is_allowed():
    require_confidence_for_estimate(DataKind.CALCULATED, None)  # no raise


def test_estimated_with_confidence_is_allowed():
    require_confidence_for_estimate(DataKind.ESTIMATED, 0.8)  # no raise


def test_confidence_out_of_range_rejected_even_when_present():
    with pytest.raises(ValueError):
        require_confidence_for_estimate(DataKind.ESTIMATED, 1.2)
