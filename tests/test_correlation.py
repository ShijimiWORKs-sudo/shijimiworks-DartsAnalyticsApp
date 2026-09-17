import pytest

from dartsanalytics.integrated.correlation import (
    MAX_CORRELATION_CONFIDENCE,
    MIN_SAMPLES_FOR_CORRELATION,
    compute_form_correlation,
)


def test_returns_none_below_minimum_sample_size():
    samples = [(float(i), float(i)) for i in range(MIN_SAMPLES_FOR_CORRELATION - 1)]
    assert compute_form_correlation("body_tilt_deg", "vertical_bias", samples) is None


def test_computes_perfect_positive_correlation():
    samples = [(float(i), float(i)) for i in range(10)]
    result = compute_form_correlation("body_tilt_deg", "vertical_bias", samples)
    assert result is not None
    assert result.pearson_r == pytest.approx(1.0)
    assert result.n == 10


def test_computes_perfect_negative_correlation():
    samples = [(float(i), -float(i)) for i in range(10)]
    result = compute_form_correlation("body_tilt_deg", "vertical_bias", samples)
    assert result is not None
    assert result.pearson_r == pytest.approx(-1.0)


def test_returns_none_when_one_axis_has_zero_variance():
    samples = [(5.0, float(i)) for i in range(10)]  # x is constant
    assert compute_form_correlation("body_tilt_deg", "vertical_bias", samples) is None


def test_confidence_scales_with_n_but_is_capped():
    small = compute_form_correlation("f", "o", [(float(i), float(i)) for i in range(5)])
    large = compute_form_correlation("f", "o", [(float(i), float(i)) for i in range(50)])
    assert small.confidence < large.confidence
    assert large.confidence <= MAX_CORRELATION_CONFIDENCE


def test_confidence_never_exceeds_documented_cap():
    result = compute_form_correlation("f", "o", [(float(i), float(i)) for i in range(1000)])
    assert result.confidence <= MAX_CORRELATION_CONFIDENCE


def test_result_is_tagged_estimated():
    from dartsanalytics.common.enums import DataKind

    result = compute_form_correlation("f", "o", [(float(i), float(i)) for i in range(10)])
    assert result.data_kind is DataKind.ESTIMATED


def test_to_dict_is_json_serializable():
    import json

    result = compute_form_correlation("body_tilt_deg", "vertical_bias", [(float(i), float(i)) for i in range(10)])
    json.dumps(result.to_dict(), ensure_ascii=False)
