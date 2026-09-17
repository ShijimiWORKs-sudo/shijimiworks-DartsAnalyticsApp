"""Tests for pose/quality_integration.py (release-readiness.md 未解決事項8:
動画品質チェックの4項目とPose解析confidenceとの結線)."""

from __future__ import annotations

import pytest

from dartsanalytics.pose.analysis import VideoPoseResult
from dartsanalytics.pose.landmarks import LandmarkPoint, PoseFrame
from dartsanalytics.pose.quality_integration import (
    LANDMARK_VISIBILITY_CONFIDENCE_THRESHOLD,
    LIMB_CONFIDENCE_THRESHOLD,
    enrich_quality_result_with_pose,
)
from dartsanalytics.video.quality import QualityCheck, QualityCheckResult
from dartsanalytics.video.ffmpeg_tools import VideoMetadata

FULL_BODY_POINTS = {
    "nose": (0.5, 0.1),
    "left_shoulder": (0.4, 0.2),
    "right_shoulder": (0.6, 0.2),
    "left_hip": (0.4, 0.5),
    "right_hip": (0.6, 0.5),
    "left_knee": (0.4, 0.7),
    "right_knee": (0.6, 0.7),
    "left_ankle": (0.4, 0.95),
    "right_ankle": (0.6, 0.95),
}


def _full_body_frame(*, confidence: float = 0.9, include: set[str] | None = None) -> PoseFrame:
    names = include if include is not None else set(FULL_BODY_POINTS)
    points = {name: LandmarkPoint(x=x, y=y, confidence=confidence) for name, (x, y) in FULL_BODY_POINTS.items() if name in names}
    # Always include the dominant-arm limb landmarks too, at the same confidence,
    # unless the caller is specifically testing their absence.
    points.setdefault("right_elbow", LandmarkPoint(x=0.65, y=0.35, confidence=confidence))
    points.setdefault("right_wrist", LandmarkPoint(x=0.7, y=0.3, confidence=confidence))
    return PoseFrame(points=points)


def _metadata() -> VideoMetadata:
    return VideoMetadata(width=1920, height=1080, fps=30.0, duration_sec=4.0, codec="h264")


def _base_result() -> QualityCheckResult:
    checks = [
        QualityCheck("resolution", True, "ok"),
        QualityCheck("fps", True, "ok"),
        QualityCheck("duration", True, "ok"),
        QualityCheck("brightness", True, "ok"),
        QualityCheck("sharpness", True, "ok"),
        QualityCheck("body_fully_visible", None, "not yet assessed"),
        QualityCheck("limbs_not_occluded", None, "not yet assessed"),
        QualityCheck("board_visible", None, "not assessable"),
        QualityCheck("release_visible", None, "not yet assessed"),
    ]
    return QualityCheckResult(metadata=_metadata(), checks=checks, grade="C", ng_reasons=[], not_assessed=[])


def _pose_result(
    *,
    frames: list[PoseFrame | None],
    release_candidates: list = None,
) -> VideoPoseResult:
    detected = sum(1 for f in frames if f is not None)
    return VideoPoseResult(
        sample_timestamps=[float(i) for i in range(len(frames))],
        frames=frames,
        features=[None] * len(frames),
        release_candidates=release_candidates or [],
        detection_rate=detected / len(frames) if frames else 0.0,
    )


def test_all_frames_fully_visible_passes_body_check():
    frames = [_full_body_frame(confidence=0.9) for _ in range(10)]
    pose_result = _pose_result(frames=frames)
    enriched = enrich_quality_result_with_pose(_base_result(), pose_result)

    body_check = next(c for c in enriched.checks if c.name == "body_fully_visible")
    assert body_check.passed is True


def test_low_confidence_landmarks_fail_body_check():
    below_threshold = LANDMARK_VISIBILITY_CONFIDENCE_THRESHOLD - 0.1
    frames = [_full_body_frame(confidence=below_threshold) for _ in range(10)]
    pose_result = _pose_result(frames=frames)
    enriched = enrich_quality_result_with_pose(_base_result(), pose_result)

    body_check = next(c for c in enriched.checks if c.name == "body_fully_visible")
    assert body_check.passed is False


def test_missing_ankles_fail_body_check_even_with_high_confidence_elsewhere():
    partial = {"nose", "left_shoulder", "right_shoulder", "left_hip", "right_hip", "left_knee", "right_knee"}
    frames = [_full_body_frame(confidence=0.95, include=partial) for _ in range(10)]
    pose_result = _pose_result(frames=frames)
    enriched = enrich_quality_result_with_pose(_base_result(), pose_result)

    body_check = next(c for c in enriched.checks if c.name == "body_fully_visible")
    assert body_check.passed is False
    assert "9件" in body_check.detail or "0件" in body_check.detail  # visible_count should be 0/10


def test_no_person_detected_in_any_frame_fails_rather_than_stays_none():
    frames: list[PoseFrame | None] = [None] * 5
    pose_result = _pose_result(frames=frames)
    enriched = enrich_quality_result_with_pose(_base_result(), pose_result)

    body_check = next(c for c in enriched.checks if c.name == "body_fully_visible")
    limbs_check = next(c for c in enriched.checks if c.name == "limbs_not_occluded")
    assert body_check.passed is False
    assert limbs_check.passed is False


def test_occluded_dominant_wrist_fails_limbs_check():
    frames = []
    for _ in range(10):
        frame = _full_body_frame(confidence=0.9)
        # Overwrite the dominant-arm wrist with a below-threshold confidence.
        points = dict(frame.points)
        points["right_wrist"] = LandmarkPoint(x=0.7, y=0.3, confidence=LIMB_CONFIDENCE_THRESHOLD - 0.1)
        frames.append(PoseFrame(points=points))

    pose_result = _pose_result(frames=frames)
    enriched = enrich_quality_result_with_pose(_base_result(), pose_result, dominant_side="right")

    limbs_check = next(c for c in enriched.checks if c.name == "limbs_not_occluded")
    assert limbs_check.passed is False
    # body_fully_visible does not depend on wrist landmarks, so it should
    # still pass — occlusion of the throwing wrist is limbs_not_occluded's
    # job specifically, not a "body not fully visible" signal.
    body_check = next(c for c in enriched.checks if c.name == "body_fully_visible")
    assert body_check.passed is True


def test_left_dominant_side_checks_left_limb_landmarks():
    frames = []
    for _ in range(10):
        frame = _full_body_frame(confidence=0.9)
        points = dict(frame.points)
        points["left_elbow"] = LandmarkPoint(x=0.35, y=0.35, confidence=0.9)
        points["left_wrist"] = LandmarkPoint(x=0.3, y=0.3, confidence=0.9)
        frames.append(PoseFrame(points=points))

    pose_result = _pose_result(frames=frames)
    enriched = enrich_quality_result_with_pose(_base_result(), pose_result, dominant_side="left")

    limbs_check = next(c for c in enriched.checks if c.name == "limbs_not_occluded")
    assert limbs_check.passed is True


def test_invalid_dominant_side_rejected():
    pose_result = _pose_result(frames=[_full_body_frame()])
    with pytest.raises(ValueError):
        enrich_quality_result_with_pose(_base_result(), pose_result, dominant_side="up")


def test_release_candidate_present_passes_release_visible():
    from dartsanalytics.pose.release import ReleaseCandidate

    candidate = ReleaseCandidate(frame_index=3, timestamp_sec=1.2, velocity=0.8, confidence=0.6)
    pose_result = _pose_result(frames=[_full_body_frame()] * 5, release_candidates=[candidate])
    enriched = enrich_quality_result_with_pose(_base_result(), pose_result)

    release_check = next(c for c in enriched.checks if c.name == "release_visible")
    assert release_check.passed is True
    assert "0.60" in release_check.detail  # confidence surfaced, never inflated


def test_no_release_candidates_fails_release_visible():
    pose_result = _pose_result(frames=[_full_body_frame()] * 5, release_candidates=[])
    enriched = enrich_quality_result_with_pose(_base_result(), pose_result)

    release_check = next(c for c in enriched.checks if c.name == "release_visible")
    assert release_check.passed is False


def test_board_visible_is_never_touched():
    pose_result = _pose_result(frames=[_full_body_frame()] * 5)
    enriched = enrich_quality_result_with_pose(_base_result(), pose_result)

    board_check = next(c for c in enriched.checks if c.name == "board_visible")
    assert board_check.passed is None


def test_grade_recomputed_after_enrichment():
    # All-passing pose result should improve the grade from the base "C"
    # (3 not-assessed checks previously counted as neither pass nor fail;
    # once they all become real passes, only board_visible remains
    # not-assessed, so grade should reflect an A/B outcome, not stay C).
    from dartsanalytics.pose.release import ReleaseCandidate

    candidate = ReleaseCandidate(frame_index=1, timestamp_sec=0.5, velocity=1.0, confidence=0.5)
    frames = [_full_body_frame(confidence=0.9) for _ in range(10)]
    pose_result = _pose_result(frames=frames, release_candidates=[candidate])

    enriched = enrich_quality_result_with_pose(_base_result(), pose_result)
    assert enriched.grade == "A"
    assert "board_visible" in enriched.not_assessed
    assert "body_fully_visible" not in enriched.not_assessed


def test_grade_downgrades_when_pose_checks_fail():
    frames: list[PoseFrame | None] = [None] * 5  # nobody detected -> body/limbs fail
    pose_result = _pose_result(frames=frames, release_candidates=[])
    enriched = enrich_quality_result_with_pose(_base_result(), pose_result)

    assert enriched.grade in ("B", "C")
    assert "body_fully_visible" in enriched.ng_reasons[0] or any(
        "body_fully_visible" in r for r in enriched.ng_reasons
    )
