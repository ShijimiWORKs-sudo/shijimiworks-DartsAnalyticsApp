import pytest

from dartsanalytics.video.quality import assess_video_quality
from tests.fixtures.video_fixtures import make_test_video


def test_good_video_grades_a_or_b(tmp_path):
    """A patterned (sharp), correctly-lit, high-res/fps clip should not be
    flagged reshoot — it may still lose a point if the synthetic pattern's
    average brightness happens to sit near a threshold, so allow A or B."""
    video = make_test_video(tmp_path / "good.mp4", width=1920, height=1080, fps=30, duration=4.0)
    result = assess_video_quality(video)
    assert result.grade in ("A", "B")
    hard_checks = {c.name: c for c in result.checks if c.name in ("resolution", "fps", "duration")}
    assert all(c.passed for c in hard_checks.values())


def test_low_resolution_video_forces_reshoot(tmp_path):
    video = make_test_video(tmp_path / "lowres.mp4", width=640, height=480, fps=30, duration=4.0)
    result = assess_video_quality(video)
    assert result.grade == "reshoot"
    assert any("resolution" in reason for reason in result.ng_reasons)


def test_low_fps_video_forces_reshoot(tmp_path):
    video = make_test_video(tmp_path / "lowfps.mp4", width=1920, height=1080, fps=15, duration=4.0)
    result = assess_video_quality(video)
    assert result.grade == "reshoot"
    assert any("fps" in reason for reason in result.ng_reasons)


def test_too_short_video_forces_reshoot(tmp_path):
    video = make_test_video(tmp_path / "short.mp4", width=1920, height=1080, fps=30, duration=1.0)
    result = assess_video_quality(video)
    assert result.grade == "reshoot"
    assert any("duration" in reason for reason in result.ng_reasons)


def test_all_black_video_flagged_for_brightness_and_sharpness(tmp_path):
    video = make_test_video(
        tmp_path / "dark.mp4", width=1920, height=1080, fps=30, duration=4.0, source="color=c=black"
    )
    result = assess_video_quality(video)
    checks_by_name = {c.name: c for c in result.checks}
    assert checks_by_name["brightness"].passed is False
    assert checks_by_name["sharpness"].passed is False  # uniform color -> zero edge variance
    # Two soft failures, no hard failures -> grade C (see quality.py rubric)
    assert result.grade == "C"


def test_not_assessed_checks_are_listed_not_silently_dropped(tmp_path):
    video = make_test_video(tmp_path / "good.mp4", duration=4.0)
    result = assess_video_quality(video)
    assert "body_fully_visible" in result.not_assessed
    assert "limbs_not_occluded" in result.not_assessed
    assert "board_visible" in result.not_assessed
    assert "release_visible" in result.not_assessed


def test_result_to_dict_is_json_serializable(tmp_path):
    import json

    video = make_test_video(tmp_path / "good.mp4", duration=4.0)
    result = assess_video_quality(video)
    json.dumps(result.to_dict(), ensure_ascii=False)  # must not raise
