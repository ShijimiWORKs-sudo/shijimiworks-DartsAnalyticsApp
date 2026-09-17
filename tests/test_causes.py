import pytest

from dartsanalytics.integrated.causes import (
    CORRELATION_THRESHOLD_FOR_CANDIDATE,
    MAX_CAUSE_CONFIDENCE,
    generate_candidate_causes,
)
from dartsanalytics.integrated.correlation import FormCorrelation


def _corr(feature, r, n=10, confidence=0.5) -> FormCorrelation:
    return FormCorrelation(form_feature_name=feature, outcome_metric_name="vertical_bias", n=n, pearson_r=r, confidence=confidence)


def test_empty_correlations_yield_empty_causes():
    assert generate_candidate_causes([]) == []


def test_strong_correlation_on_mapped_feature_produces_a_candidate():
    causes = generate_candidate_causes([_corr("right_elbow_angle_deg", 0.8)])
    assert len(causes) == 1
    assert causes[0].category == "肘/前腕角度"
    assert "断定" in causes[0].description  # explicitly disclaims certainty


def test_weak_correlation_is_not_proposed():
    causes = generate_candidate_causes([_corr("right_elbow_angle_deg", 0.2)])
    assert causes == []


def test_correlation_exactly_at_threshold_is_included():
    causes = generate_candidate_causes([_corr("right_elbow_angle_deg", CORRELATION_THRESHOLD_FOR_CANDIDATE)])
    assert len(causes) == 1


def test_unmapped_feature_name_is_skipped_not_guessed():
    causes = generate_candidate_causes([_corr("some_unknown_feature", 0.9)])
    assert causes == []


def test_negative_correlation_also_counts_by_magnitude():
    causes = generate_candidate_causes([_corr("body_tilt_deg", -0.9)])
    assert len(causes) == 1
    assert causes[0].category == "頭部/体幹移動"


def test_grip_features_map_to_grip_category():
    for feature in ("wrist_angle_deg", "barrel_axis_deg", "thumb_curl_angle_deg"):
        causes = generate_candidate_causes([_corr(feature, 0.9)])
        assert causes[0].category == "グリップ"


def test_confidence_never_exceeds_cap():
    causes = generate_candidate_causes([_corr("shoulder_tilt_deg", 1.0, confidence=0.7)])
    assert causes[0].confidence <= MAX_CAUSE_CONFIDENCE


def test_data_kind_is_advice():
    from dartsanalytics.common.enums import DataKind

    causes = generate_candidate_causes([_corr("shoulder_tilt_deg", 0.9)])
    assert causes[0].data_kind is DataKind.ADVICE


def test_multiple_correlations_can_each_produce_a_cause():
    causes = generate_candidate_causes(
        [_corr("right_elbow_angle_deg", 0.9), _corr("shoulder_tilt_deg", 0.8), _corr("weak_one", 0.1)]
    )
    categories = {c.category for c in causes}
    assert categories == {"肘/前腕角度", "肩の開き"}
