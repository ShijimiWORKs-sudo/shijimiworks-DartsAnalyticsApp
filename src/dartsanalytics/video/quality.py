"""Video quality checks (docs §7 撮影品質基準, §Phase4完了条件).

Checks are split into two kinds, and the split is load-bearing for the
"解析不能なものを無理に判定しない" design principle:

- Checks this module CAN actually assess from metadata + sampled frames
  (resolution, fps, brightness, blur) get a real pass/fail.
- Checks the spec lists that require pose/object detection (全身が映って
  いるか、肘/手首が隠れていないか、ボードが映っているか、リリースが見える
  か) are NOT_ASSESSED here — Phase 5 (pose) doesn't exist yet. They are
  still listed in the result (as passed=None) so callers/UI know these
  dimensions of quality remain unverified, rather than silently omitting
  them or worse, reporting a fabricated pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dartsanalytics.video.ffmpeg_tools import VideoMetadata, extract_sample_frames_gray, probe_metadata
from dartsanalytics.video.frame_metrics import laplacian_variance, mean_brightness

ALGORITHM_VERSION = "video_quality_v1"

# Thresholds (docs §7 必須 / 解析NG例). Named constants so a later phase can
# tune them without hunting through logic.
MIN_SHORT_SIDE_PX = 1080
MIN_LONG_SIDE_PX = 1920
MIN_FPS = 30.0
MIN_DURATION_SEC = 3.0  # shorter than this can't even hold the 3s start/end stills
MIN_BRIGHTNESS = 40.0  # below this: 強い逆光/暗すぎる
MAX_BRIGHTNESS = 235.0  # above this: 白飛び/露出過多
MIN_SHARPNESS = 15.0  # Laplacian variance; below this: 激しい手ブレ/ピンボケ


@dataclass(frozen=True)
class QualityCheck:
    name: str
    passed: bool | None  # None = not assessed (needs Phase 5+ pose/object detection)
    detail: str

    def to_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass(frozen=True)
class QualityCheckResult:
    metadata: VideoMetadata
    checks: list[QualityCheck]
    grade: str  # "A" | "B" | "C" | "reshoot"
    ng_reasons: list[str]
    not_assessed: list[str]

    def to_dict(self) -> dict:
        return {
            "metadata": self.metadata.to_dict(),
            "checks": [c.to_dict() for c in self.checks],
            "grade": self.grade,
            "ng_reasons": self.ng_reasons,
            "not_assessed": self.not_assessed,
        }


# Checks the spec requires but assess_video_quality() alone cannot assess —
# either because no pose/object detector has been run against this video,
# or (board_visible) because no detector for it exists in this codebase at
# all. Listed explicitly rather than silently skipped.
#
# body_fully_visible / limbs_not_occluded / release_visible ARE assessable
# now that Phase 5 (dartsanalytics.pose) exists — but only once pose
# analysis has actually been run against this specific video (a separate,
# comparatively expensive step this function does not perform on its own).
# A caller that already has a `VideoPoseResult` for this video should pass
# both results through pose.quality_integration.enrich_quality_result_with_
# pose() to replace these three placeholders with real pass/fail checks.
#
# board_visible remains permanently None here: it needs a board/throw-line
# OBJECT detector, which is a different capability from the body-pose
# landmarker Phase 5 implements, and no such detector exists in this
# codebase in any phase (board calibration, dartsanalytics.board, works
# from a separate static board photo, not from frames of the player).
_NOT_ASSESSED_CHECKS = [
    ("body_fully_visible", "全身が画面内に収まっているか — pose分析結果が未提供のため未評価"),
    ("limbs_not_occluded", "肘・手首・手が隠れていないか — pose分析結果が未提供のため未評価"),
    ("board_visible", "ボード/スローラインが映っているか — 物体検出器が未実装のため評価不能"),
    ("release_visible", "リリース視認性 — pose分析結果が未提供のため未評価"),
]


def assess_video_quality(path: str | Path, *, sample_frame_count: int = 5) -> QualityCheckResult:
    metadata = probe_metadata(path)
    checks: list[QualityCheck] = []

    short_side, long_side = min(metadata.width, metadata.height), max(metadata.width, metadata.height)
    resolution_ok = short_side >= MIN_SHORT_SIDE_PX and long_side >= MIN_LONG_SIDE_PX
    checks.append(
        QualityCheck(
            "resolution",
            resolution_ok,
            f"{metadata.width}x{metadata.height} (need >= {MIN_LONG_SIDE_PX}x{MIN_SHORT_SIDE_PX} "
            "or the 90°-rotated equivalent)",
        )
    )

    fps_ok = metadata.fps >= MIN_FPS
    checks.append(QualityCheck("fps", fps_ok, f"{metadata.fps:.2f}fps (need >= {MIN_FPS:.0f}fps)"))

    duration_ok = metadata.duration_sec >= MIN_DURATION_SEC
    checks.append(
        QualityCheck(
            "duration",
            duration_ok,
            f"{metadata.duration_sec:.1f}s (need >= {MIN_DURATION_SEC:.0f}s)",
        )
    )

    # Brightness/sharpness need actual frames — only bother extracting them
    # if the video is even long enough to sample meaningfully.
    if duration_ok:
        frames = extract_sample_frames_gray(path, count=sample_frame_count, metadata=metadata)
        brightness_values = [mean_brightness(f) for f in frames]
        sharpness_values = [laplacian_variance(f) for f in frames]
        avg_brightness = sum(brightness_values) / len(brightness_values)
        avg_sharpness = sum(sharpness_values) / len(sharpness_values)

        brightness_ok = MIN_BRIGHTNESS <= avg_brightness <= MAX_BRIGHTNESS
        checks.append(
            QualityCheck(
                "brightness",
                brightness_ok,
                f"avg luminance {avg_brightness:.1f} (need {MIN_BRIGHTNESS:.0f}-{MAX_BRIGHTNESS:.0f}); "
                f"逆光/暗すぎる or 露出過多 otherwise",
            )
        )

        sharpness_ok = avg_sharpness >= MIN_SHARPNESS
        checks.append(
            QualityCheck(
                "sharpness",
                sharpness_ok,
                f"Laplacian variance {avg_sharpness:.1f} (need >= {MIN_SHARPNESS:.0f}); "
                f"手ブレ/ピンボケの可能性 otherwise",
            )
        )
    else:
        checks.append(QualityCheck("brightness", None, "動画が短すぎるためスキップ"))
        checks.append(QualityCheck("sharpness", None, "動画が短すぎるためスキップ"))

    for name, detail in _NOT_ASSESSED_CHECKS:
        checks.append(QualityCheck(name, None, detail))

    return finalize_quality_result(metadata, checks)


# Checks that block a "reshoot"-free grade outright (missing/insufficient
# footage) vs. checks that only downgrade A -> B -> C. Exposed at module
# level (not buried inside assess_video_quality) so a caller who replaces
# some checks after the fact — e.g. pose.quality_integration filling in the
# not-yet-assessed pose-dependent checks with real pass/fail results — can
# recompute grade/ng_reasons/not_assessed with the exact same rule, instead
# of duplicating (and risking drifting from) this logic.
HARD_CHECK_NAMES = {"resolution", "fps", "duration"}


def finalize_quality_result(metadata: VideoMetadata, checks: list[QualityCheck]) -> QualityCheckResult:
    """Compute grade/ng_reasons/not_assessed from a finished `checks` list.

    Shared by `assess_video_quality` and by anything that later enriches an
    existing `QualityCheckResult` with additional checks (e.g. replacing a
    not-assessed pose-dependent check with a real pass/fail once pose
    analysis has actually run) — see pose/quality_integration.py.
    """
    hard_failed = [c for c in checks if c.name in HARD_CHECK_NAMES and c.passed is False]
    soft_failed = [c for c in checks if c.name not in HARD_CHECK_NAMES and c.passed is False]
    not_assessed = [c.name for c in checks if c.passed is None]

    if hard_failed:
        grade = "reshoot"
    elif len(soft_failed) == 0:
        grade = "A"
    elif len(soft_failed) == 1:
        grade = "B"
    else:
        grade = "C"

    ng_reasons = [f"{c.name}: {c.detail}" for c in checks if c.passed is False]

    return QualityCheckResult(
        metadata=metadata,
        checks=checks,
        grade=grade,
        ng_reasons=ng_reasons,
        not_assessed=not_assessed,
    )
