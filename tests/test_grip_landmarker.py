"""Tests against the real mediapipe HandLandmarker + downloaded model
(models/hand_landmarker.task — see models/README.md).

IMPORTANT LIMITATION (see docs/codex/reports/phase6_notes.md): no real
grip photo is available in this environment, so these tests can only
verify the "no hand detected" path is handled correctly (a real, honest
signal — no false positives on noise) plus error handling. They do NOT
verify detection accuracy on an actual grip photo. Skipped automatically
if the model file hasn't been downloaded (see models/README.md) so the
rest of the suite still runs without it.
"""

from pathlib import Path

import numpy as np
import pytest

from dartsanalytics.grip.landmarker import DEFAULT_MODEL_PATH, HandLandmarkerSession, HandModelNotFoundError

pytestmark = pytest.mark.skipif(
    not DEFAULT_MODEL_PATH.exists(),
    reason=f"hand landmark model not downloaded — see models/README.md ({DEFAULT_MODEL_PATH})",
)


def test_missing_model_raises_clear_error(tmp_path):
    with pytest.raises(HandModelNotFoundError):
        HandLandmarkerSession(model_path=tmp_path / "does_not_exist.task")


def test_noise_image_returns_no_detection_not_a_guess():
    with HandLandmarkerSession() as session:
        noise = (np.random.default_rng(0).random((480, 640, 3)) * 255).astype(np.uint8)
        result = session.process(noise)
        assert result is None  # correct: no false-positive hand detection


def test_blank_image_returns_no_detection():
    with HandLandmarkerSession() as session:
        blank = np.full((480, 640, 3), 128, dtype=np.uint8)
        result = session.process(blank)
        assert result is None


def test_process_rejects_wrong_shape():
    with HandLandmarkerSession() as session:
        with pytest.raises(ValueError):
            session.process(np.zeros((480, 640), dtype=np.uint8))  # missing channel dim


def test_session_context_manager_closes_cleanly():
    with HandLandmarkerSession() as session:
        assert session is not None
    # no exception on exit; a second independent session can still be created
    with HandLandmarkerSession():
        pass
