"""End-to-end Phase 4 (video sampling) + Phase 5 (pose) pipeline test.

Same limitation as test_pose_landmarker.py: no real human footage
available, so this can only prove the full pipeline runs cleanly and
reports "no detection" honestly on a person-free synthetic video — not
that detection is accurate on real footage.
"""

import pytest

from dartsanalytics.pose.analysis import analyze_video_pose
from dartsanalytics.pose.landmarker import DEFAULT_MODEL_PATH
from tests.fixtures.video_fixtures import make_test_video

pytestmark = pytest.mark.skipif(
    not DEFAULT_MODEL_PATH.exists(),
    reason=f"pose model not downloaded — see models/README.md ({DEFAULT_MODEL_PATH})",
)


def test_analyze_video_pose_on_person_free_video_reports_zero_detection(tmp_path):
    video = make_test_video(tmp_path / "no_person.mp4", width=640, height=480, fps=30, duration=3.0)
    result = analyze_video_pose(video, sample_count=3)

    assert len(result.frames) == 3
    assert all(f is None for f in result.frames)
    assert all(f is None for f in result.features)
    assert result.detection_rate == 0.0
    assert result.release_candidates == []  # no wrist track at all -> no candidates


def test_analyze_video_pose_rejects_invalid_dominant_side(tmp_path):
    video = make_test_video(tmp_path / "v.mp4", duration=2.0)
    with pytest.raises(ValueError):
        analyze_video_pose(video, dominant_side="both")


def test_analyze_video_pose_result_is_json_serializable(tmp_path):
    import json

    video = make_test_video(tmp_path / "v.mp4", duration=2.0)
    result = analyze_video_pose(video, sample_count=2)
    json.dumps(result.to_dict(), ensure_ascii=False)  # must not raise
