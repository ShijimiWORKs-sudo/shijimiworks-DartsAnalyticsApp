"""MediaPipe PoseLandmarker wrapper (docs §Phase5 姿勢推定のみ).

New dependency, flagged per AGENTS.md: `mediapipe` (already needed a real
pose-estimation model — hand-rolling one is out of scope) PLUS a one-time
local model-file download (models/README.md) since the installed
mediapipe version only exposes the Tasks API, which loads its model from a
.task file rather than bundling one in the wheel. No network access is
needed at *run* time, only once during setup.

IMPORTANT (flagged for pre-release review — see docs/codex/reports/
phase5_notes.md): this wrapper has only been exercised against a
no-person synthetic image in this session (correctly returns None, no
false positive). There is no real human throwing-motion footage available
here to validate detection accuracy, landmark placement, or confidence
calibration against. Treat pose output as unverified until tested against
real footage.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from dartsanalytics.pose.landmarks import NAMED_LANDMARK_INDEX, LandmarkPoint, PoseFrame

DEFAULT_MODEL_PATH = Path("models") / "pose_landmarker_lite.task"
MODEL_DOWNLOAD_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)
ALGORITHM_VERSION = "pose_landmarker_lite_v1"


class PoseModelNotFoundError(RuntimeError):
    def __init__(self, path: Path):
        super().__init__(
            f"Pose landmark model not found at {path}. One-time setup:\n"
            f"  curl -L -o {path} {MODEL_DOWNLOAD_URL}\n"
            "See models/README.md."
        )


class PoseLandmarkerSession:
    """Reusable session wrapping mediapipe's PoseLandmarker — create once,
    call process() per sampled frame (loading the model per-frame would be
    wasteful for a multi-frame video)."""

    def __init__(self, model_path: str | Path = DEFAULT_MODEL_PATH, *, num_poses: int = 1):
        model_path = Path(model_path)
        if not model_path.exists():
            raise PoseModelNotFoundError(model_path)

        # Imported lazily so importing dartsanalytics.pose doesn't require
        # mediapipe to be importable just to read, e.g., landmarks.py types.
        import mediapipe as mp
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core.base_options import BaseOptions

        self._mp = mp
        base_options = BaseOptions(model_asset_path=str(model_path))
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_poses=num_poses,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)

    def __enter__(self) -> "PoseLandmarkerSession":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        self._landmarker.close()

    def process(self, rgb_frame: np.ndarray) -> PoseFrame | None:
        """rgb_frame: HxWx3 uint8 array, RGB channel order. Returns None if
        no person was detected (never fabricates a result — 解析不能なもの
        を無理に判定しない)."""
        if rgb_frame.ndim != 3 or rgb_frame.shape[2] != 3:
            raise ValueError(f"expected an HxWx3 RGB array, got shape {rgb_frame.shape}")

        mp_image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB, data=rgb_frame.astype(np.uint8)
        )
        result = self._landmarker.detect(mp_image)
        if not result.pose_landmarks:
            return None

        raw_landmarks = result.pose_landmarks[0]  # first detected person only (num_poses=1 default)
        points: dict[str, LandmarkPoint] = {}
        for name, idx in NAMED_LANDMARK_INDEX.items():
            if idx >= len(raw_landmarks):
                continue
            lm = raw_landmarks[idx]
            confidence = getattr(lm, "visibility", None)
            confidence = 1.0 if confidence is None else max(0.0, min(1.0, confidence))
            points[name] = LandmarkPoint(x=lm.x, y=lm.y, confidence=confidence)

        return PoseFrame(points=points)
