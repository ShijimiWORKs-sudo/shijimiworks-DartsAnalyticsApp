"""Calibration tests against synthetic images (docs §Phase3: static images
first). No real board photos exist yet — a dark disk on a light background
is a stand-in that exercises the same code path (thresholding, connected
component, centroid/radius, circularity confidence) without needing a
real photo fixture in the repo.
"""

import numpy as np
import pytest
from PIL import Image, ImageDraw

from dartsanalytics.board.calibration import calibrate_from_array, calibrate_from_image
from dartsanalytics.common.confidence import MissingConfidenceError


def _synthetic_board_array(size=200, center=(100, 100), radius=70, malformed=False):
    img = Image.new("L", (size, size), color=230)  # light background
    draw = ImageDraw.Draw(img)
    if not malformed:
        cx, cy = center
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=40)
    return np.array(img, dtype=np.float64)


def test_calibrate_from_array_finds_known_center_and_radius():
    arr = _synthetic_board_array(size=200, center=(100, 100), radius=70)
    result = calibrate_from_array(arr)
    assert result.center_x_px == pytest.approx(100, abs=2)
    assert result.center_y_px == pytest.approx(100, abs=2)
    assert result.radius_px == pytest.approx(70, abs=3)
    assert result.confidence > 0.9  # a clean disk should be near-perfectly circular


def test_calibrate_from_array_handles_off_center_board():
    arr = _synthetic_board_array(size=300, center=(120, 160), radius=50)
    result = calibrate_from_array(arr)
    assert result.center_x_px == pytest.approx(120, abs=2)
    assert result.center_y_px == pytest.approx(160, abs=2)


def test_calibrate_from_array_low_confidence_when_nothing_found():
    """Malformed/blank input ('解析不能なものを無理に判定しない') must not be
    reported as a confident detection."""
    arr = np.full((100, 100), 128.0)  # perfectly flat, nothing to threshold
    result = calibrate_from_array(arr)
    assert result.confidence == 0.0


def test_calibrate_from_array_rejects_non_2d_input():
    with pytest.raises(ValueError):
        calibrate_from_array(np.zeros((10, 10, 3)))


def test_calibration_requires_confidence_field_present():
    arr = _synthetic_board_array()
    result = calibrate_from_array(arr)
    assert result.confidence is not None  # constructing with None would raise
    with pytest.raises(MissingConfidenceError):
        type(result)(
            center_x_px=0, center_y_px=0, radius_px=1, algorithm_version="x", confidence=None
        )


def test_calibrate_from_image_matches_calibrate_from_array(tmp_path):
    arr = _synthetic_board_array(size=200, center=(90, 110), radius=60)
    path = tmp_path / "board.png"
    Image.fromarray(arr.astype("uint8"), mode="L").save(path)

    from_array = calibrate_from_array(arr)
    from_image = calibrate_from_image(path)

    assert from_image.center_x_px == pytest.approx(from_array.center_x_px, abs=2)
    assert from_image.center_y_px == pytest.approx(from_array.center_y_px, abs=2)
    assert from_image.radius_px == pytest.approx(from_array.radius_px, abs=3)


def test_calibrate_from_image_downsamples_large_images_consistently(tmp_path):
    """A large image should still calibrate close to the true center after
    the internal downsample-then-scale-back path (calibration.py
    _MAX_CALIBRATION_DIMENSION)."""
    arr = _synthetic_board_array(size=1000, center=(600, 350), radius=300)
    path = tmp_path / "big_board.png"
    Image.fromarray(arr.astype("uint8"), mode="L").save(path)

    result = calibrate_from_image(path)
    assert result.center_x_px == pytest.approx(600, abs=10)
    assert result.center_y_px == pytest.approx(350, abs=10)
    assert result.radius_px == pytest.approx(300, abs=15)
