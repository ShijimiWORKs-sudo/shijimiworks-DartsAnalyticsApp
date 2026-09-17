import numpy as np
import pytest

from dartsanalytics.video.frame_metrics import laplacian_variance, mean_brightness


def test_mean_brightness_black_and_white():
    black = np.zeros((50, 50))
    white = np.full((50, 50), 255.0)
    assert mean_brightness(black) == 0.0
    assert mean_brightness(white) == 255.0


def test_mean_brightness_gray_midpoint():
    gray = np.full((50, 50), 128.0)
    assert mean_brightness(gray) == pytest.approx(128.0)


def test_laplacian_variance_zero_for_uniform_image():
    uniform = np.full((50, 50), 100.0)
    assert laplacian_variance(uniform) == pytest.approx(0.0)


def test_laplacian_variance_higher_for_checkerboard_than_uniform():
    checkerboard = np.indices((50, 50)).sum(axis=0) % 2 * 255.0
    uniform = np.full((50, 50), 128.0)
    assert laplacian_variance(checkerboard) > laplacian_variance(uniform)


def test_laplacian_variance_rejects_too_small_frame():
    with pytest.raises(ValueError):
        laplacian_variance(np.zeros((2, 2)))
