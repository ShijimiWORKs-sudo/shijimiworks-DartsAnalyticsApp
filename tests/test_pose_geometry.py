import pytest

from dartsanalytics.pose.geometry import joint_angle_deg, midpoint, tilt_from_horizontal_deg, tilt_from_vertical_deg


def test_midpoint():
    assert midpoint((0.0, 0.0), (2.0, 4.0)) == (1.0, 2.0)


def test_joint_angle_straight_line_is_180():
    # a --- vertex --- c, collinear -> fully "extended" elbow
    angle = joint_angle_deg((0.0, 0.0), (1.0, 0.0), (2.0, 0.0))
    assert angle == pytest.approx(180.0)


def test_joint_angle_right_angle_is_90():
    angle = joint_angle_deg((1.0, 0.0), (0.0, 0.0), (0.0, 1.0))
    assert angle == pytest.approx(90.0)


def test_joint_angle_fully_bent_is_near_zero():
    angle = joint_angle_deg((1.0, 0.0), (0.0, 0.0), (1.0, 0.0001))
    assert angle == pytest.approx(0.0, abs=1.0)


def test_joint_angle_rejects_degenerate_input():
    with pytest.raises(ValueError):
        joint_angle_deg((0.0, 0.0), (0.0, 0.0), (1.0, 0.0))  # vertex == a


def test_tilt_from_vertical_perfectly_upright_is_zero():
    # top directly "above" bottom in image coords (smaller pixel y)
    angle = tilt_from_vertical_deg(bottom=(5.0, 10.0), top=(5.0, 0.0))
    assert angle == pytest.approx(0.0)


def test_tilt_from_vertical_leaning_right_is_positive():
    angle = tilt_from_vertical_deg(bottom=(5.0, 10.0), top=(6.0, 0.0))
    assert angle > 0


def test_tilt_from_vertical_leaning_left_is_negative():
    angle = tilt_from_vertical_deg(bottom=(5.0, 10.0), top=(4.0, 0.0))
    assert angle < 0


def test_tilt_from_vertical_rejects_degenerate_input():
    with pytest.raises(ValueError):
        tilt_from_vertical_deg(bottom=(1.0, 1.0), top=(1.0, 1.0))


def test_tilt_from_horizontal_level_is_zero():
    angle = tilt_from_horizontal_deg(left=(0.0, 5.0), right=(10.0, 5.0))
    assert angle == pytest.approx(0.0)


def test_tilt_from_horizontal_right_side_higher_is_positive():
    # right point has smaller pixel-y (higher in the image)
    angle = tilt_from_horizontal_deg(left=(0.0, 5.0), right=(10.0, 2.0))
    assert angle > 0


def test_tilt_from_horizontal_rejects_degenerate_input():
    with pytest.raises(ValueError):
        tilt_from_horizontal_deg(left=(2.0, 2.0), right=(2.0, 2.0))
