"""Ties grip-photo intake + hand landmark detection + feature computation
into a two-photo (dominant side + opposite side) grip analysis
(docs §8: 左右2方向を基本とする).

Dart/barrel object detection itself is out of scope in this phase — see
grip/features.py module docstring for what barrel_axis_deg actually is
(a hand-geometry proxy, not a detected barrel). This module only tracks
hand landmarks and derives finger/wrist geometry from them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from dartsanalytics.grip.features import GripFeatures, compute_grip_features
from dartsanalytics.grip.landmarker import DEFAULT_MODEL_PATH, HandLandmarkerSession
from dartsanalytics.grip.landmarks import HandFrame

# docs §8: "写真からは指先・関節・バレル軸等を推定するが、2D画像だけで実際の
# 接触圧や完全な3Dグリップを断定しない。" Surfaced explicitly on every result
# so callers/reports never have to infer scope from silence.
NOT_ASSESSED: tuple[str, ...] = (
    "contact_pressure",  # 2D images cannot measure finger-to-barrel contact force
    "full_3d_grip_structure",  # a single 2D photo per side cannot reconstruct true 3D grip
    "barrel_object_geometry",  # no dart/barrel object detection — barrel_axis_deg is a hand-landmark proxy only
)

VALID_SIDES = ("dominant", "opposite")


def _load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as img:
        return np.array(img.convert("RGB"))


@dataclass(frozen=True)
class GripPhotoResult:
    side: str  # "dominant" or "opposite"
    detected: bool
    frame: HandFrame | None
    features: GripFeatures | None

    def to_dict(self) -> dict:
        return {
            "side": self.side,
            "detected": self.detected,
            "frame": self.frame.to_dict() if self.frame else None,
            "features": self.features.to_dict() if self.features else None,
        }


@dataclass(frozen=True)
class GripAnalysisResult:
    dominant: GripPhotoResult
    opposite: GripPhotoResult | None
    not_assessed: tuple[str, ...] = field(default_factory=lambda: NOT_ASSESSED)

    def to_dict(self) -> dict:
        return {
            "dominant": self.dominant.to_dict(),
            "opposite": self.opposite.to_dict() if self.opposite else None,
            "not_assessed": list(self.not_assessed),
        }


def _analyze_with_session(path: str | Path, *, side: str, session: HandLandmarkerSession) -> GripPhotoResult:
    if side not in VALID_SIDES:
        raise ValueError(f"side must be one of {VALID_SIDES}, got {side!r}")
    rgb = _load_rgb(Path(path))
    frame = session.process(rgb)
    features = compute_grip_features(frame) if frame else None
    return GripPhotoResult(side=side, detected=frame is not None, frame=frame, features=features)


def analyze_grip_photo(
    path: str | Path, *, side: str, model_path: str | Path = DEFAULT_MODEL_PATH
) -> GripPhotoResult:
    """Analyze a single grip photo. Opens its own HandLandmarkerSession —
    for analyzing both sides together, prefer analyze_grip_photos (shares
    one session, avoiding loading the model twice)."""
    with HandLandmarkerSession(model_path=model_path) as session:
        return _analyze_with_session(path, side=side, session=session)


def analyze_grip_photos(
    dominant_path: str | Path,
    opposite_path: str | Path | None = None,
    *,
    model_path: str | Path = DEFAULT_MODEL_PATH,
) -> GripAnalysisResult:
    """docs §8: 左右2方向を基本とする — opposite_path is optional so a
    dominant-side-only intake still produces a (partial) result rather than
    failing outright."""
    with HandLandmarkerSession(model_path=model_path) as session:
        dominant = _analyze_with_session(dominant_path, side="dominant", session=session)
        opposite = (
            _analyze_with_session(opposite_path, side="opposite", session=session) if opposite_path else None
        )
    return GripAnalysisResult(dominant=dominant, opposite=opposite)
