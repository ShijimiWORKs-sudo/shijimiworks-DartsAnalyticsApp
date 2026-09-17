"""Tests for recalibration-prompt logic (docs §7)."""

from __future__ import annotations

import pytest

from dartsanalytics.board.calibration import BoardCalibration
from dartsanalytics.board.recalibration import (
    DEFAULT_CENTER_DRIFT_THRESHOLD,
    DEFAULT_CONFIDENCE_FLOOR,
    assess_recalibration_need,
)


def _cal(cx=100.0, cy=100.0, r=50.0, conf=0.9) -> BoardCalibration:
    return BoardCalibration(center_x_px=cx, center_y_px=cy, radius_px=r, algorithm_version="v", confidence=conf)


def test_no_previous_calibration_only_checks_absolute_floor():
    result = assess_recalibration_need(_cal(conf=0.9))
    assert result.recalibration_recommended is False
    assert result.confidence_drop is None


def test_low_absolute_confidence_alone_triggers_recommendation():
    result = assess_recalibration_need(_cal(conf=DEFAULT_CONFIDENCE_FLOOR - 0.01))
    assert result.recalibration_recommended is True
    assert any("below the floor" in r for r in result.reasons)


def test_stable_calibration_across_two_frames_does_not_trigger():
    previous = _cal(cx=100.0, cy=100.0, r=50.0, conf=0.85)
    current = _cal(cx=100.5, cy=99.5, r=50.2, conf=0.83)  # tiny, expected jitter
    result = assess_recalibration_need(current, previous)
    assert result.recalibration_recommended is False


def test_sharp_confidence_drop_triggers_even_if_still_above_floor():
    previous = _cal(conf=0.9)
    current = _cal(conf=0.6)  # still "fine" in absolute terms but a big drop
    result = assess_recalibration_need(current, previous)
    assert result.recalibration_recommended is True
    assert result.confidence_drop == pytest.approx(0.3)
    assert any("dropped" in r for r in result.reasons)


def test_center_drift_triggers_even_with_unchanged_confidence():
    previous = _cal(cx=100.0, cy=100.0, r=50.0, conf=0.9)
    # Center moved by 10px on a radius-50 board -> 20% drift, well above the 5% default.
    current = _cal(cx=110.0, cy=100.0, r=50.0, conf=0.9)
    result = assess_recalibration_need(current, previous)
    assert result.recalibration_recommended is True
    assert result.center_drift_normalized == pytest.approx(0.2)
    assert any("center drifted" in r for r in result.reasons)


def test_radius_drift_triggers_camera_distance_warning():
    previous = _cal(r=50.0, conf=0.9)
    current = _cal(r=65.0, conf=0.9)  # 30% larger -> camera likely moved closer
    result = assess_recalibration_need(current, previous)
    assert result.recalibration_recommended is True
    assert result.radius_drift_ratio == pytest.approx(0.3)
    assert any("radius changed" in r for r in result.reasons)


def test_custom_thresholds_are_respected():
    previous = _cal(cx=100.0, cy=100.0, r=50.0, conf=0.9)
    current = _cal(cx=102.0, cy=100.0, r=50.0, conf=0.9)  # 4% drift
    default_result = assess_recalibration_need(current, previous)
    assert default_result.recalibration_recommended is False  # under the 5% default

    strict_result = assess_recalibration_need(
        current, previous, center_drift_threshold=0.03
    )
    assert strict_result.recalibration_recommended is True
    assert strict_result.center_drift_normalized == pytest.approx(DEFAULT_CENTER_DRIFT_THRESHOLD - 0.01)
