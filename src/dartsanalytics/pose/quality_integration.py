"""Wires Phase 5 pose-detection output into video/quality.py's previously
not-assessed checks (release-readiness.md 未解決事項8: 「動画品質チェック
の4項目...とPose解析confidenceとの結線」).

Background: `video.quality.assess_video_quality()` was written before Phase
5 (this `pose` package) existed, so it left 4 checks the spec (docs §7)
requires as `passed=None` ("not assessed"): body_fully_visible,
limbs_not_occluded, board_visible, release_visible. Phase 5 now exists and
can genuinely inform 3 of these 4 — this module fills those 3 in with real
pass/fail results computed from an already-run `VideoPoseResult`, and
leaves `board_visible` permanently `None` (see video/quality.py's
_NOT_ASSESSED_CHECKS docstring: it needs an object/board detector, a
different capability from the body-pose landmarker, which does not exist
in this codebase in any phase).

This module does NOT run pose analysis itself — `analyze_video_pose()` is a
separate, comparatively expensive step (model inference over sampled
frames) the caller runs once and passes in, rather than this module
silently re-running it. Kept in the `pose` package (not `video`) so the
existing one-directional dependency (pose -> video) doesn't become a
cycle — video.quality never imports from pose.
"""

from __future__ import annotations

from dartsanalytics.pose.analysis import VideoPoseResult
from dartsanalytics.pose.landmarks import PoseFrame
from dartsanalytics.video.quality import QualityCheck, QualityCheckResult, finalize_quality_result

# "Full body" here means the head-to-ankle silhouette the spec's 全身可視性
# check cares about — NOT the wrists (a throwing-arm wrist naturally leaves
# frame briefly during backswing without meaning the body isn't "fully
# visible"; wrist-specific occlusion is limbs_not_occluded's job instead).
FULL_BODY_LANDMARKS: tuple[str, ...] = (
    "nose",
    "left_shoulder",
    "right_shoulder",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)

# A documented convention, not a measured/calibrated constant (same caveat
# as recalibration.py's thresholds and grouping.py's cep_radius): 0.5
# matches ConfidenceLevel.REFERENCE's floor (common/confidence.py) so a
# landmark below "reference-grade" confidence doesn't count as visible.
LANDMARK_VISIBILITY_CONFIDENCE_THRESHOLD = 0.5

# Fraction of sampled frames that must show the full landmark set above
# threshold for body_fully_visible to pass. Below 1.0 on purpose — a
# throwing motion naturally has brief frames where the camera angle or a
# fast limb movement drops one landmark's confidence without the body
# actually having left the frame.
MIN_FULL_BODY_VISIBLE_FRAME_RATE = 0.8

# Same threshold family, applied specifically to the dominant (throwing)
# arm's elbow + wrist for limbs_not_occluded.
LIMB_CONFIDENCE_THRESHOLD = 0.5
MIN_LIMB_VISIBLE_FRAME_RATE = 0.8


def _frame_has_full_body(frame: PoseFrame) -> bool:
    for name in FULL_BODY_LANDMARKS:
        point = frame.get(name)
        if point is None or point.confidence < LANDMARK_VISIBILITY_CONFIDENCE_THRESHOLD:
            return False
    return True


def _frame_has_limbs_visible(frame: PoseFrame, dominant_side: str) -> bool:
    for name in (f"{dominant_side}_elbow", f"{dominant_side}_wrist"):
        point = frame.get(name)
        if point is None or point.confidence < LIMB_CONFIDENCE_THRESHOLD:
            return False
    return True


def _body_fully_visible_check(pose_result: VideoPoseResult) -> QualityCheck:
    detected_frames = [f for f in pose_result.frames if f is not None]
    if not detected_frames:
        return QualityCheck(
            "body_fully_visible",
            False,
            "サンプリングした全フレームで人物を検出できなかった "
            f"(detection_rate={pose_result.detection_rate:.0%})。全身可視性を判定できるだけの検出結果が無い。",
        )

    visible_count = sum(1 for f in detected_frames if _frame_has_full_body(f))
    rate = visible_count / len(detected_frames)
    passed = rate >= MIN_FULL_BODY_VISIBLE_FRAME_RATE
    return QualityCheck(
        "body_fully_visible",
        passed,
        f"人物検出フレーム{len(detected_frames)}件中{visible_count}件で頭部・肩・腰・膝・足首の"
        f"全ランドマークが信頼度{LANDMARK_VISIBILITY_CONFIDENCE_THRESHOLD}以上で検出された "
        f"({rate:.0%}, 基準: {MIN_FULL_BODY_VISIBLE_FRAME_RATE:.0%}以上)。",
    )


def _limbs_not_occluded_check(pose_result: VideoPoseResult, dominant_side: str) -> QualityCheck:
    detected_frames = [f for f in pose_result.frames if f is not None]
    if not detected_frames:
        return QualityCheck(
            "limbs_not_occluded",
            False,
            f"サンプリングした全フレームで人物を検出できなかった (detection_rate={pose_result.detection_rate:.0%})。"
            "肘・手首の隠れを判定できるだけの検出結果が無い。",
        )

    visible_count = sum(1 for f in detected_frames if _frame_has_limbs_visible(f, dominant_side))
    rate = visible_count / len(detected_frames)
    passed = rate >= MIN_LIMB_VISIBLE_FRAME_RATE
    return QualityCheck(
        "limbs_not_occluded",
        passed,
        f"人物検出フレーム{len(detected_frames)}件中{visible_count}件で利き腕"
        f"({dominant_side})の肘・手首が信頼度{LIMB_CONFIDENCE_THRESHOLD}以上で検出された "
        f"({rate:.0%}, 基準: {MIN_LIMB_VISIBLE_FRAME_RATE:.0%}以上)。",
    )


def _release_visible_check(pose_result: VideoPoseResult) -> QualityCheck:
    if not pose_result.release_candidates:
        return QualityCheck(
            "release_visible",
            False,
            "リリース候補（手首速度のピーク）を検出できなかった — "
            "利き腕の手首が十分な頻度で検出されていない可能性がある。",
        )

    top = pose_result.release_candidates[0]
    return QualityCheck(
        "release_visible",
        True,
        f"リリース候補を検出（{top.timestamp_sec:.2f}秒、速度{top.velocity:.3f}、"
        f"ヒューリスティック確信度{top.confidence:.2f}）。手首速度ピークに基づく候補であり、"
        "実際のリリース瞬間そのものの確定ではない点に注意。",
    )


def enrich_quality_result_with_pose(
    result: QualityCheckResult,
    pose_result: VideoPoseResult,
    *,
    dominant_side: str = "right",
) -> QualityCheckResult:
    """Return a new `QualityCheckResult` with body_fully_visible /
    limbs_not_occluded / release_visible replaced by real assessments
    computed from `pose_result` (an already-run `analyze_video_pose()`
    result for the SAME video `result` was computed from — this function
    has no way to verify that precondition, so the caller must ensure it).

    `board_visible` is left untouched (stays `passed=None`) — see this
    module's docstring for why.
    """
    if dominant_side not in ("left", "right"):
        raise ValueError(f"dominant_side must be 'left' or 'right', got {dominant_side!r}")

    replacements = {
        "body_fully_visible": _body_fully_visible_check(pose_result),
        "limbs_not_occluded": _limbs_not_occluded_check(pose_result, dominant_side),
        "release_visible": _release_visible_check(pose_result),
    }

    new_checks = [replacements.get(c.name, c) for c in result.checks]
    return finalize_quality_result(result.metadata, new_checks)
