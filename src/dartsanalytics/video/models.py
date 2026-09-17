"""MediaAsset entity — mirrors the `media_assets` table (db/schema/0001_initial.sql).

Kept in the video module (not dartsanalytics.models.entities) since it's
Phase-4-specific; entities.py holds the Phase 0/1 core types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

from dartsanalytics.video.angles import ShootingAngle


def _new_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MediaAsset:
    session_id: str
    media_type: str  # "video" | "photo"
    file_path: str
    media_id: str = field(default_factory=_new_id)
    angle: ShootingAngle | None = None
    checksum: str | None = None
    quality_grade: str | None = None  # "A" | "B" | "C" | "reshoot" | None
    created_at: str = field(default_factory=_now_iso)

    def __post_init__(self) -> None:
        if self.media_type not in ("video", "photo"):
            raise ValueError(f"media_type must be 'video' or 'photo', got {self.media_type!r}")
        if self.quality_grade not in (None, "A", "B", "C", "reshoot"):
            raise ValueError(f"invalid quality_grade: {self.quality_grade!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "media_id": self.media_id,
            "session_id": self.session_id,
            "media_type": self.media_type,
            "file_path": self.file_path,
            "angle": self.angle.value if self.angle else None,
            "checksum": self.checksum,
            "quality_grade": self.quality_grade,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MediaAsset":
        data = dict(data)
        if data.get("angle") is not None:
            data["angle"] = ShootingAngle(data["angle"])
        return cls(**data)
