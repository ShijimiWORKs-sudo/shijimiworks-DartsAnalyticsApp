"""Ties video frame sampling (Phase 4) + pose landmark detection + feature
computation + release-candidate detection into one per-video call.

Dart detection itself is explicitly out of scope (docs §Phase5:
"ダーツ自体の認識は別モジュール") — this module only tracks body landmarks.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dartsanalytics.pose.features import PoseFeatures, compute_pose_features
from dartsanalytics.pose.landmarker import DEFAULT_MODEL_PATH, PoseLandmarkerSession
from dartsanalytics.pose.landmarks import PoseFrame
from dartsanalytics.pose.release import ReleaseCandidate, find_release_candidates
from dartsanalytics.video.ffmpeg_tools import extract_sample_frames_rgb, probe_metadata, sample_timestamps


@dataclass(frozen=True)
class VideoPoseResult:
    sample_timestamps: list[float]
    frames: list[PoseFrame | None]
    features: list[PoseFeatures | None]
    release_candidates: list[ReleaseCandidate]
    detection_rate: float  # fraction of sampled frames where a person was detected

    def to_dict(self) -> dict:
        return {
            "sample_timestamps": self.sample_timestamps,
            "frames": [f.to_dict() if f else None for f in self.frames],
            "features": [f.to_dict() if f else None for f in self.features],
            "release_candidates": [c.to_dict() for c in self.release_candidates],
            "detection_rate": self.detection_rate,
        }


def analyze_video_pose(
    path: str | Path,
    *,
    model_path: str | Path = DEFAULT_MODEL_PATH,
    sample_count: int = 10,
    dominant_side: str = "right",
) -> VideoPoseResult:
    if dominant_side not in ("left", "right"):
        raise ValueError(f"dominant_side must be 'left' or 'right', got {dominant_side!r}")

    path = Path(path)
    metadata = probe_metadata(path)
    timestamps = sample_timestamps(metadata.duration_sec, sample_count)
    rgb_frames = extract_sample_frames_rgb(path, count=sample_count, metadata=metadata)

    pose_frames: list[PoseFrame | None] = []
    features: list[PoseFeatures | None] = []
    wrist_track: list[tuple[float, float, float]] = []

    with PoseLandmarkerSession(model_path=model_path) as session:
        for ts, rgb in zip(timestamps, rgb_frames):
            pose_frame = session.process(rgb)
            pose_frames.append(pose_frame)
            features.append(compute_pose_features(pose_frame) if pose_frame else None)

            if pose_frame:
                wrist = pose_frame.get(f"{dominant_side}_wrist")
                if wrist:
                    wrist_track.append((ts, wrist.x, wrist.y))

    detected_count = sum(1 for f in pose_frames if f is not None)
    detection_rate = detected_count / len(pose_frames) if pose_frames else 0.0
    release_candidates = find_release_candidates(wrist_track, top_n=1)

    return VideoPoseResult(
        sample_timestamps=timestamps,
        frames=pose_frames,
        features=features,
        release_candidates=release_candidates,
        detection_rate=detection_rate,
    )
