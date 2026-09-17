"""MediaPipe HandLandmarker wrapper (docs §Phase6 グリップ写真解析).

No new pip dependency — Phase 5 already added `mediapipe` for pose
estimation, and HandLandmarker is the same Tasks API family. It needs its
own separately-downloaded `.task` model file though (models/README.md),
same one-time-setup, offline-afterward pattern as Phase 5's pose model.

IMPORTANT (flagged for pre-release review — see docs/codex/reports/
phase6_notes.md): this wrapper has only been exercised against
hand-free synthetic images in this session (correctly returns None, no
false positive). There are no real grip photos available here to
validate detection accuracy, landmark placement, or confidence
calibration against. Treat grip output as unverified until tested
against real photos.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from dartsanalytics.grip.landmarks import NAMED_LANDMARK_INDEX, HandFrame, HandLandmarkPoint

DEFAULT_MODEL_PATH = Path("models") / "hand_landmarker.task"
MODEL_DOWNLOAD_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)
ALGORITHM_VERSION = "hand_landmarker_v1"


class HandModelNotFoundError(RuntimeError):
    def __init__(self, path: Path):
        super().__init__(
            f"Hand landmark model not found at {path}. One-time setup:\n"
            f"  curl -L -o {path} {MODEL_DOWNLOAD_URL}\n"
            "See models/README.md."
        )


class HandLandmarkerSession:
    """Reusable session wrapping mediapipe's HandLandmarker — create once,
    call process() per grip photo (loading the model per-call would be
    wasteful when analyzing both the dominant-side and opposite-side
    photos)."""

    def __init__(self, model_path: str | Path = DEFAULT_MODEL_PATH, *, num_hands: int = 1):
        model_path = Path(model_path)
        if not model_path.exists():
            raise HandModelNotFoundError(model_path)

        # Imported lazily so importing dartsanalytics.grip doesn't require
        # mediapipe to be importable just to read, e.g., landmarks.py types.
        import mediapipe as mp
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core.base_options import BaseOptions

        self._mp = mp
        base_options = BaseOptions(model_asset_path=str(model_path))
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_hands=num_hands,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)

    def __enter__(self) -> "HandLandmarkerSession":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        self._landmarker.close()

    def process(self, rgb_frame: np.ndarray) -> HandFrame | None:
        """rgb_frame: HxWx3 uint8 array, RGB channel order. Returns None if
        no hand was detected (never fabricates a result — 解析不能なもの
        を無理に判定しない)."""
        if rgb_frame.ndim != 3 or rgb_frame.shape[2] != 3:
            raise ValueError(f"expected an HxWx3 RGB array, got shape {rgb_frame.shape}")

        mp_image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB, data=rgb_frame.astype(np.uint8)
        )
        result = self._landmarker.detect(mp_image)
        if not result.hand_landmarks:
            return None

        raw_landmarks = result.hand_landmarks[0]  # first detected hand only (num_hands=1 default)

        # HandLandmarker (unlike PoseLandmarker) does not expose a
        # per-landmark visibility/presence score in this API surface — the
        # only confidence signal is the handedness classification score,
        # applied here uniformly to every landmark. Documented limitation,
        # not a silent assumption (see landmarks.py HandLandmarkPoint docstring).
        handedness_score = 1.0
        handedness_label: str | None = None
        if result.handedness and result.handedness[0]:
            top = result.handedness[0][0]
            handedness_score = max(0.0, min(1.0, top.score))
            handedness_label = top.category_name

        points: dict[str, HandLandmarkPoint] = {}
        for name, idx in NAMED_LANDMARK_INDEX.items():
            if idx >= len(raw_landmarks):
                continue
            lm = raw_landmarks[idx]
            points[name] = HandLandmarkPoint(x=lm.x, y=lm.y, confidence=handedness_score)

        return HandFrame(points=points, handedness=handedness_label)
