import pytest

from dartsanalytics.grip.features import (
    MAX_BARREL_AXIS_CONFIDENCE,
    MIN_BARREL_AXIS_CONFIDENCE,
    compute_grip_features,
)
from dartsanalytics.grip.landmarks import HandFrame, HandLandmarkPoint


def _pt(x, y, conf=0.9) -> HandLandmarkPoint:
    return HandLandmarkPoint(x=x, y=y, confidence=conf)


def test_full_frame_produces_all_features():
    frame = HandFrame(
        points={
            "wrist": _pt(0.5, 0.9, 0.9),
            "thumb_mcp": _pt(0.4, 0.8, 0.85),
            "thumb_ip": _pt(0.35, 0.6, 0.8),
            "thumb_tip": _pt(0.3, 0.4, 0.75),
            "index_mcp": _pt(0.55, 0.75, 0.9),
            "index_pip": _pt(0.6, 0.55, 0.85),
            "index_tip": _pt(0.65, 0.35, 0.8),
            "middle_mcp": _pt(0.6, 0.7, 0.9),
            "middle_pip": _pt(0.65, 0.5, 0.85),
            "middle_tip": _pt(0.7, 0.3, 0.8),
        }
    )
    features = compute_grip_features(frame)
    assert features.thumb_curl_angle_deg is not None
    assert features.index_curl_angle_deg is not None
    assert features.middle_curl_angle_deg is not None
    assert features.wrist_angle_deg is not None
    assert features.barrel_axis_deg is not None


def test_missing_landmarks_yield_none_not_a_guess():
    frame = HandFrame(points={"wrist": _pt(0.5, 0.5)})  # everything else missing
    features = compute_grip_features(frame)
    assert features.thumb_curl_angle_deg is None
    assert features.index_curl_angle_deg is None
    assert features.middle_curl_angle_deg is None
    assert features.wrist_angle_deg is None
    assert features.barrel_axis_deg is None


def test_finger_curl_confidence_is_min_of_contributing_landmarks():
    frame = HandFrame(
        points={
            "thumb_mcp": _pt(0.4, 0.8, 0.95),
            "thumb_ip": _pt(0.35, 0.6, 0.30),  # lowest confidence of the three
            "thumb_tip": _pt(0.3, 0.4, 0.80),
        }
    )
    features = compute_grip_features(frame)
    assert features.thumb_curl_angle_deg is not None
    assert features.thumb_curl_angle_deg.confidence == pytest.approx(0.30)


def test_barrel_axis_confidence_is_always_capped_low():
    """barrel_axis_deg is a hand-geometry proxy, not a detected barrel —
    its confidence must never approach the finger/wrist angles' own
    confidence, even when the contributing landmarks are near-certain."""
    frame = HandFrame(
        points={
            "thumb_tip": _pt(0.3, 0.4, 1.0),
            "index_tip": _pt(0.65, 0.35, 1.0),
        }
    )
    features = compute_grip_features(frame)
    assert features.barrel_axis_deg is not None
    assert features.barrel_axis_deg.confidence <= MAX_BARREL_AXIS_CONFIDENCE
    assert features.barrel_axis_deg.confidence < 0.75  # never claims "十分" (sufficient) or higher


def test_barrel_axis_confidence_respects_documented_bounds():
    frame = HandFrame(
        points={
            "thumb_tip": _pt(0.3, 0.4, 0.01),
            "index_tip": _pt(0.65, 0.35, 0.01),
        }
    )
    features = compute_grip_features(frame)
    assert features.barrel_axis_deg is not None
    assert MIN_BARREL_AXIS_CONFIDENCE <= features.barrel_axis_deg.confidence <= MAX_BARREL_AXIS_CONFIDENCE


def test_all_feature_values_tagged_estimated():
    from dartsanalytics.common.enums import DataKind

    frame = HandFrame(
        points={
            "wrist": _pt(0.5, 0.9),
            "middle_mcp": _pt(0.6, 0.7),
        }
    )
    features = compute_grip_features(frame)
    assert features.wrist_angle_deg.data_kind is DataKind.ESTIMATED


def test_degenerate_landmark_positions_yield_none_not_a_crash():
    """Coincident points (a bad/degenerate detection) must not propagate a
    math error out of compute_grip_features."""
    frame = HandFrame(
        points={
            "wrist": _pt(0.5, 0.5),
            "middle_mcp": _pt(0.5, 0.5),  # identical to wrist -> degenerate line
        }
    )
    features = compute_grip_features(frame)
    assert features.wrist_angle_deg is None
