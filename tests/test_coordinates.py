import math

import pytest

from dartsanalytics.board.calibration import BoardCalibration
from dartsanalytics.board.coordinates import normalize_point


def _calibration(cx=100.0, cy=100.0, r=50.0):
    return BoardCalibration(
        center_x_px=cx, center_y_px=cy, radius_px=r, algorithm_version="test", confidence=0.9
    )


def test_center_pixel_normalizes_to_origin():
    p = normalize_point(100.0, 100.0, _calibration())
    assert p.normalized_x == pytest.approx(0.0)
    assert p.normalized_y == pytest.approx(0.0)
    assert p.distance_from_bull == pytest.approx(0.0)


def test_right_of_center_is_positive_x():
    p = normalize_point(150.0, 100.0, _calibration())  # 50px right, at radius
    assert p.normalized_x == pytest.approx(1.0)
    assert p.normalized_y == pytest.approx(0.0)
    assert p.angle_deg == pytest.approx(0.0)


def test_above_center_in_image_is_positive_normalized_y():
    """Pixel y grows downward; 'above center' in the photo (smaller pixel y)
    must map to positive normalized_y (up-positive convention, see
    coordinates.py docstring)."""
    p = normalize_point(100.0, 50.0, _calibration())  # 50px UP from center
    assert p.normalized_y == pytest.approx(1.0)
    assert p.angle_deg == pytest.approx(90.0)


def test_below_center_in_image_is_negative_normalized_y():
    p = normalize_point(100.0, 150.0, _calibration())  # 50px DOWN from center
    assert p.normalized_y == pytest.approx(-1.0)
    assert p.angle_deg == pytest.approx(-90.0)


def test_distance_from_bull_matches_pythagorean_distance():
    p = normalize_point(130.0, 60.0, _calibration())  # 30 right, 40 up -> dist 50px -> 1.0 normalized
    assert p.distance_from_bull == pytest.approx(1.0)


def test_rejects_zero_or_negative_radius_calibration():
    bad_calibration = BoardCalibration(
        center_x_px=0, center_y_px=0, radius_px=0, algorithm_version="test", confidence=0.9
    )
    with pytest.raises(ValueError):
        normalize_point(1.0, 1.0, bad_calibration)
