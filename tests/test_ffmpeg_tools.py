import pytest

from dartsanalytics.video.ffmpeg_tools import (
    FFmpegNotFoundError,
    VideoProbeError,
    extract_sample_frames_gray,
    probe_metadata,
)
from tests.fixtures.video_fixtures import make_test_video


def test_probe_metadata_reports_correct_resolution_and_duration(tmp_path):
    video = make_test_video(tmp_path / "v.mp4", width=1280, height=720, fps=30, duration=3.0)
    meta = probe_metadata(video)
    assert meta.width == 1280
    assert meta.height == 720
    assert meta.fps == pytest.approx(30.0, abs=0.1)
    assert meta.duration_sec == pytest.approx(3.0, abs=0.3)
    assert meta.codec is not None


@pytest.mark.parametrize("fps", [24, 60])
def test_probe_metadata_reports_correct_fps(tmp_path, fps):
    video = make_test_video(tmp_path / "v.mp4", width=640, height=480, fps=fps, duration=1.0)
    meta = probe_metadata(video)
    assert meta.fps == pytest.approx(fps, abs=0.1)


def test_probe_metadata_missing_file_raises_probe_error(tmp_path):
    with pytest.raises(VideoProbeError):
        probe_metadata(tmp_path / "does_not_exist.mp4")


def test_probe_metadata_missing_binary_raises_clear_error(tmp_path, monkeypatch):
    video = make_test_video(tmp_path / "v.mp4", duration=1.0)
    monkeypatch.setenv("PATH", "")
    with pytest.raises(FFmpegNotFoundError):
        probe_metadata(video)


def test_extract_sample_frames_gray_returns_requested_count_and_shape(tmp_path):
    video = make_test_video(tmp_path / "v.mp4", width=320, height=240, fps=30, duration=2.0)
    meta = probe_metadata(video)
    frames = extract_sample_frames_gray(video, count=3, metadata=meta)
    assert len(frames) == 3
    for frame in frames:
        assert frame.shape == (240, 320)


def test_extract_sample_frames_gray_single_frame(tmp_path):
    video = make_test_video(tmp_path / "v.mp4", duration=2.0)
    frames = extract_sample_frames_gray(video, count=1)
    assert len(frames) == 1


def test_extract_sample_frames_gray_rejects_zero_count(tmp_path):
    video = make_test_video(tmp_path / "v.mp4", duration=2.0)
    with pytest.raises(ValueError):
        extract_sample_frames_gray(video, count=0)
