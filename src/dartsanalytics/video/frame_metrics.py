"""No-ML frame-level image metrics used by quality checks.

Deliberately simple, well-understood techniques (mean luminance, Laplacian
variance) rather than a learned model — Phase 4 is about basic intake
quality gating, not content understanding (that's Phase 5's pose work).
"""

from __future__ import annotations

import numpy as np


def mean_brightness(gray: np.ndarray) -> float:
    """0 (black) .. 255 (white) average luminance."""
    return float(gray.mean())


def laplacian_variance(gray: np.ndarray) -> float:
    """Classic no-ML blur metric: variance of the discrete Laplacian.

    A sharp image has strong edges -> high-variance Laplacian response; a
    blurry one is smooth -> low variance. Implemented via array slicing
    (5-point stencil) rather than a general convolution to avoid adding
    scipy for one operator.
    """
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        raise ValueError(f"frame too small for Laplacian ({gray.shape}); need >= 3x3")
    center = gray[1:-1, 1:-1]
    up = gray[:-2, 1:-1]
    down = gray[2:, 1:-1]
    left = gray[1:-1, :-2]
    right = gray[1:-1, 2:]
    laplacian = up + down + left + right - 4 * center
    return float(laplacian.var())
