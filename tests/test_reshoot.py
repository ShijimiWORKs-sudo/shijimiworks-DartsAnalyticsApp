from dartsanalytics.video.angles import ShootingAngle
from dartsanalytics.video.models import MediaAsset
from dartsanalytics.video.reshoot import (
    missing_required_angles,
    recommend_additional_angles,
    summarize_session_intake,
)


def test_missing_required_angles_all_missing_when_empty():
    missing = missing_required_angles({})
    assert len(missing) == 4


def test_missing_required_angles_excludes_satisfied_ones():
    captured = {
        ShootingAngle.FRONT: "A",
        ShootingAngle.DOMINANT_SIDE: "B",
        ShootingAngle.OPPOSITE_SIDE: "reshoot",
        # WIDE not captured at all
    }
    missing = missing_required_angles(captured)
    assert set(missing) == {ShootingAngle.OPPOSITE_SIDE, ShootingAngle.WIDE}


def test_recommend_additional_angles_empty_when_all_good():
    captured = {a: "A" for a in [ShootingAngle.FRONT, ShootingAngle.DOMINANT_SIDE]}
    assert recommend_additional_angles(captured) == []


def test_recommend_additional_angles_on_borderline_dominant_side():
    captured = {ShootingAngle.DOMINANT_SIDE: "C"}
    recs = recommend_additional_angles(captured)
    assert ShootingAngle.HAND_CLOSEUP in recs


def test_summarize_session_intake_tracks_best_grade_per_angle():
    assets = [
        MediaAsset(session_id="s1", media_type="video", file_path="a.mp4", angle=ShootingAngle.FRONT, quality_grade="B"),
        MediaAsset(session_id="s1", media_type="video", file_path="b.mp4", angle=ShootingAngle.FRONT, quality_grade="A"),
        MediaAsset(session_id="s1", media_type="video", file_path="c.mp4", angle=ShootingAngle.DOMINANT_SIDE, quality_grade="reshoot"),
    ]
    summary = summarize_session_intake(assets)
    assert summary["best_grade_by_angle"]["front"] == "A"  # best of B, A
    assert "opposite_side" in summary["missing_required_angles"]
    assert "wide" in summary["missing_required_angles"]
    assert "dominant_side" in summary["missing_required_angles"]  # only reshoot-grade so far
    assert summary["all_required_satisfied"] is False


def test_summarize_session_intake_all_satisfied():
    assets = [
        MediaAsset(session_id="s1", media_type="video", file_path=f"{a.value}.mp4", angle=a, quality_grade="A")
        for a in [ShootingAngle.FRONT, ShootingAngle.DOMINANT_SIDE, ShootingAngle.OPPOSITE_SIDE, ShootingAngle.WIDE]
    ]
    summary = summarize_session_intake(assets)
    assert summary["all_required_satisfied"] is True
    assert summary["missing_required_angles"] == []
