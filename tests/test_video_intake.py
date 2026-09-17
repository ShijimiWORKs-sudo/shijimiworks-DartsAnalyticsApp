import pytest

from dartsanalytics.video.angles import ShootingAngle
from dartsanalytics.video.intake import compute_checksum, ingest_video
from dartsanalytics.video.models import MediaAsset
from tests.fixtures.video_fixtures import make_test_video


def test_compute_checksum_is_deterministic_and_sha256_shaped(tmp_path):
    video = make_test_video(tmp_path / "v.mp4", duration=1.0)
    a = compute_checksum(video)
    b = compute_checksum(video)
    assert a == b
    assert len(a) == 64  # sha256 hex digest length
    int(a, 16)  # must be valid hex


def test_compute_checksum_differs_for_different_content(tmp_path):
    v1 = make_test_video(tmp_path / "v1.mp4", duration=1.0, source="color=c=black")
    v2 = make_test_video(tmp_path / "v2.mp4", duration=1.0, source="color=c=white")
    assert compute_checksum(v1) != compute_checksum(v2)


def test_ingest_video_builds_media_asset_with_quality_grade(tmp_path):
    video = make_test_video(tmp_path / "v.mp4", width=1920, height=1080, fps=30, duration=4.0)
    asset, quality_result = ingest_video(video, session_id="s1", angle=ShootingAngle.FRONT)
    assert asset.session_id == "s1"
    assert asset.angle is ShootingAngle.FRONT
    assert asset.media_type == "video"
    assert asset.quality_grade == quality_result.grade
    assert asset.checksum == compute_checksum(video)
    assert asset.file_path == str(video)


def test_ingest_video_never_modifies_source_file(tmp_path):
    video = make_test_video(tmp_path / "v.mp4", duration=2.0)
    before = video.stat().st_mtime_ns
    before_checksum = compute_checksum(video)
    ingest_video(video, session_id="s1", angle=ShootingAngle.WIDE)
    after = video.stat().st_mtime_ns
    after_checksum = compute_checksum(video)
    assert before == after
    assert before_checksum == after_checksum


def test_ingest_video_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        ingest_video("/nonexistent/path.mp4", session_id="s1", angle=ShootingAngle.FRONT)


def test_media_asset_rejects_invalid_media_type():
    with pytest.raises(ValueError):
        MediaAsset(session_id="s1", media_type="audio", file_path="x.mp4")


def test_media_asset_rejects_invalid_quality_grade():
    with pytest.raises(ValueError):
        MediaAsset(session_id="s1", media_type="video", file_path="x.mp4", quality_grade="F")


def test_media_asset_round_trip():
    asset = MediaAsset(
        session_id="s1",
        media_type="video",
        file_path="x.mp4",
        angle=ShootingAngle.DOMINANT_SIDE,
        checksum="abc123",
        quality_grade="A",
    )
    data = asset.to_dict()
    restored = MediaAsset.from_dict(data)
    assert restored.angle is ShootingAngle.DOMINANT_SIDE
    assert restored == asset
