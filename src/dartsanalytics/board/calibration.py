"""Board calibration: locate the dartboard's center and radius in a photo.

Phase 3 scope is explicitly static-image-first (docs §Phase3: "まず静止画像で
テストする。リアルタイム化は後回し。"). The algorithm here is intentionally
simple — threshold the board (assumed to be the largest roughly-circular,
roughly-centered region that contrasts with the surrounding background) and
take its centroid and equivalent-circle radius. This is NOT a robust
production board detector (no Hough circle transform, no ring/wire
detection, no handling of cluttered backgrounds) — it is a first pass that
Phase 3's completion condition (grouping stats recomputable from calibrated
coordinates) can build on. Treat every result as DataKind.ESTIMATED with a
confidence derived from how circular/well-centered the detected region is,
never as ground truth (design principle #10: 解析不能な動画を無理に判定しない
— the same caution applies to images).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from dartsanalytics.common.confidence import require_confidence_for_estimate
from dartsanalytics.common.enums import DataKind

ALGORITHM_VERSION = "board_calib_v1"


@dataclass(frozen=True)
class BoardCalibration:
    center_x_px: float
    center_y_px: float
    radius_px: float
    algorithm_version: str
    confidence: float
    data_kind: DataKind = DataKind.ESTIMATED

    def __post_init__(self) -> None:
        require_confidence_for_estimate(self.data_kind, self.confidence)

    def to_dict(self) -> dict:
        return {
            "center_x_px": self.center_x_px,
            "center_y_px": self.center_y_px,
            "radius_px": self.radius_px,
            "algorithm_version": self.algorithm_version,
            "confidence": self.confidence,
            "data_kind": self.data_kind.value,
        }


def _largest_component_mask(binary: np.ndarray) -> np.ndarray:
    """Return a boolean mask of the largest 4-connected True region.

    A tiny flood-fill/union-find implementation — avoids adding scipy just
    for connected-components labeling.
    """
    visited = np.zeros_like(binary, dtype=bool)
    best_mask = np.zeros_like(binary, dtype=bool)
    best_size = 0
    height, width = binary.shape

    for start_y in range(height):
        row = binary[start_y]
        if not row.any():
            continue
        for start_x in range(width):
            if not binary[start_y, start_x] or visited[start_y, start_x]:
                continue
            # BFS flood fill
            stack = [(start_y, start_x)]
            visited[start_y, start_x] = True
            component_coords = []
            while stack:
                y, x = stack.pop()
                component_coords.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if (
                        0 <= ny < height
                        and 0 <= nx < width
                        and binary[ny, nx]
                        and not visited[ny, nx]
                    ):
                        visited[ny, nx] = True
                        stack.append((ny, nx))
            if len(component_coords) > best_size:
                best_size = len(component_coords)
                best_mask = np.zeros_like(binary, dtype=bool)
                ys, xs = zip(*component_coords)
                best_mask[np.array(ys), np.array(xs)] = True

    return best_mask


def calibrate_from_array(gray: np.ndarray) -> BoardCalibration:
    """Calibrate from a 2D grayscale array (0-255).

    Assumes the board is darker or lighter than a roughly uniform
    background (Otsu-style thresholding at the midpoint between the two
    dominant intensity clusters). Confidence reflects both how circular the
    detected region is (area vs. bounding-circle area) and how large a
    fraction of the frame it occupies (too small -> board wasn't isolated
    from background; too large -> thresholding likely captured the whole
    frame, not just the board).
    """
    if gray.ndim != 2:
        raise ValueError(f"expected a 2D grayscale array, got shape {gray.shape}")

    height, width = gray.shape
    mean_intensity = float(gray.mean())
    # Two-cluster split around the mean is a crude but dependency-free stand-in
    # for Otsu thresholding; good enough for a clean board-vs-background photo.
    binary = gray < mean_intensity if gray[0, 0] > mean_intensity else gray > mean_intensity

    mask = _largest_component_mask(binary)
    area = int(mask.sum())

    if area == 0:
        # Nothing detected at all: return a center-of-frame fallback with
        # PENDING-bucket confidence rather than raising — callers decide
        # whether to ask for a re-shoot (matches "解析不能を無理に判定しない").
        return BoardCalibration(
            center_x_px=width / 2,
            center_y_px=height / 2,
            radius_px=min(width, height) / 2,
            algorithm_version=ALGORITHM_VERSION,
            confidence=0.0,
        )

    ys, xs = np.nonzero(mask)
    center_x = float(xs.mean())
    center_y = float(ys.mean())
    radius = math.sqrt(area / math.pi)  # equivalent-circle radius from area

    # Circularity: ratio of actual area to the area of the bounding circle
    # implied by the farthest mask pixel from the centroid. 1.0 = perfect
    # disk; lower values mean the region is elongated/irregular.
    max_dist = float(np.hypot(xs - center_x, ys - center_y).max())
    bounding_circle_area = math.pi * max_dist**2 if max_dist > 0 else 1.0
    circularity = min(1.0, area / bounding_circle_area) if bounding_circle_area else 0.0

    frame_area = height * width
    coverage = area / frame_area
    # Plausible board coverage in a well-framed photo; outside this range
    # we trust the detection less even if it's a perfect circle (e.g. a
    # thresholding artifact covering the whole frame is "circular" by luck).
    coverage_ok = 0.05 <= coverage <= 0.85
    confidence = circularity if coverage_ok else circularity * 0.5
    confidence = max(0.0, min(1.0, confidence))

    return BoardCalibration(
        center_x_px=center_x,
        center_y_px=center_y,
        radius_px=radius,
        algorithm_version=ALGORITHM_VERSION,
        confidence=confidence,
    )


# The connected-component labeling above is a pure-Python BFS (no scipy
# dependency) — fine for a few hundred pixels per side, but O(pixels) in
# Python is too slow on a full-resolution phone photo (multi-megapixel).
# Downsample before labeling and scale the result back up, rather than
# running the flood fill at full resolution.
_MAX_CALIBRATION_DIMENSION = 400


def calibrate_from_image(path: str | Path) -> BoardCalibration:
    with Image.open(path) as img:
        gray_img = img.convert("L")
        width, height = gray_img.size
        scale = 1.0
        longest_side = max(width, height)
        if longest_side > _MAX_CALIBRATION_DIMENSION:
            scale = _MAX_CALIBRATION_DIMENSION / longest_side
            gray_img = gray_img.resize(
                (max(1, round(width * scale)), max(1, round(height * scale))),
                Image.BILINEAR,
            )
        gray = np.array(gray_img, dtype=np.float64)

    result = calibrate_from_array(gray)
    if scale == 1.0:
        return result
    return BoardCalibration(
        center_x_px=result.center_x_px / scale,
        center_y_px=result.center_y_px / scale,
        radius_px=result.radius_px / scale,
        algorithm_version=result.algorithm_version,
        confidence=result.confidence,
    )
