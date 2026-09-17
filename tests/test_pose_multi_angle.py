"""Tests for multi-angle pose feature integration (docs §6)."""

from __future__ import annotations

import pytest

from dartsanalytics.common.enums import DataKind
from dartsanalytics.pose.features import FeatureValue, PoseFeatures
from dartsanalytics.pose.multi_angle import (
    DISAGREEMENT_THRESHOLD_DEG,
    merge_multi_angle_pose_features,
)
from dartsanalytics.video.angles import ShootingAngle


def _features(body_tilt=None, shoulder_tilt=None, elbow=None) -> PoseFeatures:
    return PoseFeatures(
        body_tilt_deg=body_tilt,
        shoulder_tilt_deg=shoulder_tilt,
        hip_tilt_deg=None,
        left_elbow_angle_deg=elbow,
        right_elbow_angle_deg=None,
    )


def test_merge_rejects_empty_input():
    with pytest.raises(ValueError):
        merge_multi_angle_pose_features({})


def test_single_angle_passes_through_unchanged():
    fv = FeatureValue(value=5.0, confidence=0.6, data_kind=DataKind.ESTIMATED)
    result = merge_multi_angle_pose_features({ShootingAngle.FRONT: _features(body_tilt=fv)})
    merged = result.merged["body_tilt_deg"]
    assert merged.value == 5.0
    assert merged.source_angle is ShootingAngle.FRONT
    assert merged.contributing_angles == (ShootingAngle.FRONT,)
    assert merged.disagreement_deg is None


def test_missing_feature_across_all_angles_is_none():
    result = merge_multi_angle_pose_features(
        {ShootingAngle.FRONT: _features(), ShootingAngle.WIDE: _features()}
    )
    assert result.merged["body_tilt_deg"] is None


def test_higher_confidence_angle_wins():
    low_conf = FeatureValue(value=3.0, confidence=0.3, data_kind=DataKind.ESTIMATED)
    high_conf = FeatureValue(value=7.0, confidence=0.8, data_kind=DataKind.ESTIMATED)
    result = merge_multi_angle_pose_features(
        {
            ShootingAngle.FRONT: _features(body_tilt=low_conf),
            ShootingAngle.DOMINANT_SIDE: _features(body_tilt=high_conf),
        }
    )
    merged = result.merged["body_tilt_deg"]
    assert merged.value == 7.0
    assert merged.confidence == 0.8
    assert merged.source_angle is ShootingAngle.DOMINANT_SIDE
    assert set(merged.contributing_angles) == {ShootingAngle.FRONT, ShootingAngle.DOMINANT_SIDE}


def test_disagreement_deg_is_max_minus_min():
    a = FeatureValue(value=2.0, confidence=0.5, data_kind=DataKind.ESTIMATED)
    b = FeatureValue(value=20.0, confidence=0.4, data_kind=DataKind.ESTIMATED)
    result = merge_multi_angle_pose_features(
        {ShootingAngle.FRONT: _features(body_tilt=a), ShootingAngle.WIDE: _features(body_tilt=b)}
    )
    merged = result.merged["body_tilt_deg"]
    assert merged.disagreement_deg == pytest.approx(18.0)


def test_disagreeing_features_flags_large_spread_but_not_small():
    large_spread_a = FeatureValue(value=0.0, confidence=0.5, data_kind=DataKind.ESTIMATED)
    large_spread_b = FeatureValue(
        value=DISAGREEMENT_THRESHOLD_DEG + 1, confidence=0.5, data_kind=DataKind.ESTIMATED
    )
    small_spread_a = FeatureValue(value=10.0, confidence=0.5, data_kind=DataKind.ESTIMATED)
    small_spread_b = FeatureValue(value=10.5, confidence=0.5, data_kind=DataKind.ESTIMATED)

    result = merge_multi_angle_pose_features(
        {
            ShootingAngle.FRONT: _features(body_tilt=large_spread_a, shoulder_tilt=small_spread_a),
            ShootingAngle.WIDE: _features(body_tilt=large_spread_b, shoulder_tilt=small_spread_b),
        }
    )
    assert result.disagreeing_features() == ["body_tilt_deg"]


def test_never_fabricates_higher_confidence_than_best_single_source():
    """The whole point of not averaging: a merge must never claim MORE
    confidence than its best contributing estimate."""
    a = FeatureValue(value=5.0, confidence=0.4, data_kind=DataKind.ESTIMATED)
    b = FeatureValue(value=6.0, confidence=0.5, data_kind=DataKind.ESTIMATED)
    result = merge_multi_angle_pose_features(
        {ShootingAngle.FRONT: _features(body_tilt=a), ShootingAngle.WIDE: _features(body_tilt=b)}
    )
    merged = result.merged["body_tilt_deg"]
    assert merged.confidence == max(a.confidence, b.confidence)
