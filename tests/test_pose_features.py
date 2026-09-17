import pytest

from dartsanalytics.pose.features import compute_pose_features
from dartsanalytics.pose.landmarks import LandmarkPoint, PoseFrame


def _pt(x, y, conf=0.9) -> LandmarkPoint:
    return LandmarkPoint(x=x, y=y, confidence=conf)


def test_full_frame_produces_all_features():
    frame = PoseFrame(
        points={
            "left_shoulder": _pt(0.3, 0.3, 0.9),
            "right_shoulder": _pt(0.7, 0.3, 0.8),
            "left_hip": _pt(0.35, 0.6, 0.85),
            "right_hip": _pt(0.65, 0.6, 0.95),
            "left_elbow": _pt(0.2, 0.45, 0.7),
            "left_wrist": _pt(0.1, 0.6, 0.6),
            "right_elbow": _pt(0.8, 0.45, 0.75),
            "right_wrist": _pt(0.9, 0.6, 0.65),
        }
    )
    features = compute_pose_features(frame)
    assert features.body_tilt_deg is not None
    assert features.shoulder_tilt_deg is not None
    assert features.hip_tilt_deg is not None
    assert features.left_elbow_angle_deg is not None
    assert features.right_elbow_angle_deg is not None


def test_missing_landmarks_yield_none_not_a_guess():
    frame = PoseFrame(points={"left_shoulder": _pt(0.3, 0.3)})  # everything else missing
    features = compute_pose_features(frame)
    assert features.body_tilt_deg is None
    assert features.shoulder_tilt_deg is None
    assert features.hip_tilt_deg is None
    assert features.left_elbow_angle_deg is None
    assert features.right_elbow_angle_deg is None


def test_elbow_angle_confidence_is_min_of_contributing_landmarks():
    frame = PoseFrame(
        points={
            "right_shoulder": _pt(0.5, 0.3, 0.95),
            "right_elbow": _pt(0.6, 0.45, 0.40),  # lowest confidence of the three
            "right_wrist": _pt(0.7, 0.6, 0.80),
        }
    )
    features = compute_pose_features(frame)
    assert features.right_elbow_angle_deg is not None
    assert features.right_elbow_angle_deg.confidence == pytest.approx(0.40)


def test_shoulder_tilt_confidence_is_min_of_two_shoulders():
    frame = PoseFrame(
        points={
            "left_shoulder": _pt(0.3, 0.3, 0.9),
            "right_shoulder": _pt(0.7, 0.3, 0.5),
        }
    )
    features = compute_pose_features(frame)
    assert features.shoulder_tilt_deg.confidence == pytest.approx(0.5)


def test_all_feature_values_tagged_estimated():
    from dartsanalytics.common.enums import DataKind

    frame = PoseFrame(
        points={
            "left_shoulder": _pt(0.3, 0.3),
            "right_shoulder": _pt(0.7, 0.3),
        }
    )
    features = compute_pose_features(frame)
    assert features.shoulder_tilt_deg.data_kind is DataKind.ESTIMATED


def test_degenerate_landmark_positions_yield_none_not_a_crash():
    """Coincident shoulder points (a bad/degenerate detection) must not
    propagate a math error out of compute_pose_features."""
    frame = PoseFrame(
        points={
            "left_shoulder": _pt(0.5, 0.5),
            "right_shoulder": _pt(0.5, 0.5),  # identical to left -> degenerate line
        }
    )
    features = compute_pose_features(frame)
    assert features.shoulder_tilt_deg is None
