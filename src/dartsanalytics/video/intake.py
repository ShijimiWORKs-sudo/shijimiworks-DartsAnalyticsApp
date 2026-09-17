"""Video import: checksum + quality assessment -> MediaAsset (docs §Phase4).

`ingest_video` never writes to, moves, or renames the source file — it
only reads it (checksum, ffprobe/ffmpeg frame sampling to a temp dir that
is cleaned up). This is the concrete implementation of "動画原本を上書き
しない" for the intake step.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from dartsanalytics.video.angles import ShootingAngle
from dartsanalytics.video.models import MediaAsset
from dartsanalytics.video.quality import QualityCheckResult, assess_video_quality

_CHECKSUM_CHUNK_SIZE = 1024 * 1024  # 1 MiB


def compute_checksum(path: str | Path) -> str:
    path = Path(path)
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHECKSUM_CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


def ingest_video(
    path: str | Path, *, session_id: str, angle: ShootingAngle
) -> tuple[MediaAsset, QualityCheckResult]:
    """Import one video: checksum it, assess quality, build its MediaAsset.

    Returns (media_asset, quality_result) — the caller decides whether to
    persist the asset (e.g. skip on 'reshoot' grade, or persist anyway and
    surface the NG reasons to the user, per UI needs). Both are returned so
    "NG理由表示" has the full detail even though only quality_grade is
    stored on the entity itself (see docs/codex/reports/status.md for why
    the full check detail isn't persisted to the DB yet).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"video not found: {path}")

    checksum = compute_checksum(path)
    quality_result = assess_video_quality(path)

    asset = MediaAsset(
        session_id=session_id,
        media_type="video",
        file_path=str(path),
        angle=angle,
        checksum=checksum,
        quality_grade=quality_result.grade,
    )
    return asset, quality_result
