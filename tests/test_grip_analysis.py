"""End-to-end grip photo intake + hand landmark detection + feature
pipeline test.

Same limitation as test_grip_landmarker.py: no real grip photo available,
so this can only prove the full pipeline runs cleanly and reports "no
detection" honestly on a hand-free synthetic photo — not that detection
is accurate on a real grip photo.
"""

import numpy as np
import pytest
from PIL import Image

from dartsanalytics.grip.analysis import NOT_ASSESSED, analyze_grip_photo, analyze_grip_photos
from dartsanalytics.grip.landmarker import DEFAULT_MODEL_PATH

pytestmark = pytest.mark.skipif(
    not DEFAULT_MODEL_PATH.exists(),
    reason=f"hand landmark model not downloaded — see models/README.md ({DEFAULT_MODEL_PATH})",
)


def _make_blank_photo(path, size=(640, 480)) -> None:
    img = Image.fromarray(np.full((size[1], size[0], 3), 128, dtype=np.uint8))
    img.save(path)


def test_analyze_grip_photo_on_hand_free_photo_reports_no_detection(tmp_path):
    photo = tmp_path / "blank.png"
    _make_blank_photo(photo)

    result = analyze_grip_photo(photo, side="dominant")
    assert result.side == "dominant"
    assert result.detected is False
    assert result.frame is None
    assert result.features is None


def test_analyze_grip_photo_rejects_invalid_side(tmp_path):
    photo = tmp_path / "blank.png"
    _make_blank_photo(photo)
    with pytest.raises(ValueError):
        analyze_grip_photo(photo, side="both")


def test_analyze_grip_photos_combines_dominant_and_opposite(tmp_path):
    dominant_photo = tmp_path / "dominant.png"
    opposite_photo = tmp_path / "opposite.png"
    _make_blank_photo(dominant_photo)
    _make_blank_photo(opposite_photo)

    result = analyze_grip_photos(dominant_photo, opposite_photo)
    assert result.dominant.side == "dominant"
    assert result.opposite is not None
    assert result.opposite.side == "opposite"
    assert result.not_assessed == NOT_ASSESSED
    assert "contact_pressure" in result.not_assessed


def test_analyze_grip_photos_opposite_is_optional(tmp_path):
    dominant_photo = tmp_path / "dominant.png"
    _make_blank_photo(dominant_photo)

    result = analyze_grip_photos(dominant_photo)
    assert result.dominant is not None
    assert result.opposite is None


def test_grip_analysis_result_is_json_serializable(tmp_path):
    import json

    dominant_photo = tmp_path / "dominant.png"
    _make_blank_photo(dominant_photo)

    result = analyze_grip_photos(dominant_photo)
    json.dumps(result.to_dict(), ensure_ascii=False)  # must not raise
