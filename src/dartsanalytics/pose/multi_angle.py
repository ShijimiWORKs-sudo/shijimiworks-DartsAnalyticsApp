"""Multi-angle pose feature integration (docs §6: "4動画は同期撮影ではない
ため、正確な同期3D軌道再構成を約束しない。特徴量を各視点から抽出し、安定
した情報を統合する").

Design choice: this module does NOT hardcode "which angle is more reliable
for which feature" (e.g. "elbow angle is more accurate from the side").
That would be a biomechanical claim this project has no measured basis for
— exactly the kind of manufactured precision the design principle
"解析不能なものを無理に判定しない" warns against. Instead, integration is
generic and honest:

  1. For each feature name, take every angle's non-None estimate.
  2. Prefer the single highest-confidence estimate as the merged value
     (confidence already reflects how much each pose-analysis run trusted
     its own landmarks — see pose/features.py).
  3. If multiple angles produced an estimate for the same feature, report
     the spread between them (max - min) rather than silently averaging
     it away. A caller/report should treat a large spread as "this
     feature is uncertain from this session's videos", not as a bug.

No new DataKind/confidence is invented for the merged value — it simply
carries over the chosen source estimate's own DataKind/confidence, so a
merge never *looks* more certain than its best single input.
"""

from __future__ import annotations

from dataclasses import dataclass

from dartsanalytics.common.enums import DataKind
from dartsanalytics.pose.features import FeatureValue, PoseFeatures
from dartsanalytics.video.angles import ShootingAngle

FEATURE_NAMES: tuple[str, ...] = (
    "body_tilt_deg",
    "shoulder_tilt_deg",
    "hip_tilt_deg",
    "left_elbow_angle_deg",
    "right_elbow_angle_deg",
)

# Above this many degrees of spread between two angles' independent
# estimates of the SAME feature, the estimates are considered to disagree
# meaningfully — not a measured biomechanical threshold, just a documented,
# overridable convention (same pattern as
# board.grouping.DEFAULT_BULL_VICINITY_RADIUS).
DISAGREEMENT_THRESHOLD_DEG = 15.0


@dataclass(frozen=True)
class MergedFeature:
    value: float
    confidence: float
    data_kind: DataKind
    source_angle: ShootingAngle
    contributing_angles: tuple[ShootingAngle, ...]
    disagreement_deg: float | None  # max-min among contributing_angles; None if only 1 contributed

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "data_kind": self.data_kind.value,
            "source_angle": self.source_angle.value,
            "contributing_angles": [a.value for a in self.contributing_angles],
            "disagreement_deg": self.disagreement_deg,
        }


@dataclass(frozen=True)
class MultiAngleMergeResult:
    merged: dict[str, MergedFeature | None]
    angles_used: tuple[ShootingAngle, ...]

    def to_dict(self) -> dict:
        return {
            "merged": {k: (v.to_dict() if v else None) for k, v in self.merged.items()},
            "angles_used": [a.value for a in self.angles_used],
        }

    def disagreeing_features(self) -> list[str]:
        """Feature names whose spread across angles exceeds
        DISAGREEMENT_THRESHOLD_DEG — surfaced explicitly so a report/UI can
        flag "this session's videos don't agree on X" rather than quietly
        presenting one angle's number as if uncontested."""
        return [
            name
            for name, mf in self.merged.items()
            if mf is not None
            and mf.disagreement_deg is not None
            and mf.disagreement_deg > DISAGREEMENT_THRESHOLD_DEG
        ]


def _feature_value(features: PoseFeatures, name: str) -> FeatureValue | None:
    return getattr(features, name)


def merge_multi_angle_pose_features(
    features_by_angle: dict[ShootingAngle, PoseFeatures]
) -> MultiAngleMergeResult:
    if not features_by_angle:
        raise ValueError("features_by_angle must not be empty")

    merged: dict[str, MergedFeature | None] = {}
    for name in FEATURE_NAMES:
        candidates: list[tuple[ShootingAngle, FeatureValue]] = [
            (angle, fv)
            for angle, features in features_by_angle.items()
            if (fv := _feature_value(features, name)) is not None
        ]
        if not candidates:
            merged[name] = None
            continue

        best_angle, best_value = max(candidates, key=lambda pair: pair[1].confidence)
        contributing = tuple(sorted((a for a, _ in candidates), key=lambda a: a.value))
        disagreement: float | None = None
        if len(candidates) > 1:
            values = [fv.value for _, fv in candidates]
            disagreement = max(values) - min(values)

        merged[name] = MergedFeature(
            value=best_value.value,
            confidence=best_value.confidence,
            data_kind=best_value.data_kind,
            source_angle=best_angle,
            contributing_angles=contributing,
            disagreement_deg=disagreement,
        )

    return MultiAngleMergeResult(merged=merged, angles_used=tuple(features_by_angle.keys()))
