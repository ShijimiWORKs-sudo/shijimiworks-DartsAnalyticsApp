"""Common entity types (Phase 0 "共通型").

Plain dataclasses, not an ORM — Phase 0/1 deliberately keep the DB layer
(raw SQL in dartsanalytics.db) and the domain model separate and simple.
Each entity has to_dict()/from_dict() for JSON export (spec §22) and DB
row round-tripping.

Field validation that encodes a project rule (e.g. "estimates need
confidence", "round_number in 1..8") lives in __post_init__ so it is
enforced no matter which code path constructs the object.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any
import uuid

from dartsanalytics.common.confidence import require_confidence_for_estimate
from dartsanalytics.common.enums import DataKind, DetectionSource, GameType, Ring, SessionStatus


def _new_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Account:
    display_name: str
    account_id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Account":
        return cls(**data)


@dataclass
class Player:
    account_id: str
    display_name: str
    player_id: str = field(default_factory=_new_id)
    dominant_hand: str | None = None  # "right" | "left" | None
    dominant_eye: str | None = None
    created_at: str = field(default_factory=_now_iso)

    def __post_init__(self) -> None:
        if self.dominant_hand not in (None, "right", "left"):
            raise ValueError(f"dominant_hand must be right/left/None, got {self.dominant_hand!r}")
        if self.dominant_eye not in (None, "right", "left"):
            raise ValueError(f"dominant_eye must be right/left/None, got {self.dominant_eye!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Player":
        return cls(**data)


@dataclass
class EquipmentProfile:
    player_id: str
    equipment_id: str = field(default_factory=_new_id)
    barrel_maker: str | None = None
    barrel_name: str | None = None
    barrel_weight_g: float | None = None
    total_weight_g: float | None = None
    flight_type: str | None = None
    shaft_type: str | None = None
    shaft_length: str | None = None
    tip_type: str | None = None
    changed_at: str = field(default_factory=_now_iso)
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EquipmentProfile":
        return cls(**data)


@dataclass
class CountupRound:
    session_id: str
    round_number: int
    round_id: str = field(default_factory=_new_id)
    round_score: int | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.round_number <= 8:
            raise ValueError(f"round_number must be 1..8, got {self.round_number}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CountupRound":
        return cls(**data)


@dataclass
class Throw:
    """One dart throw — the atomic unit of measurement (design principle #2:
    "1投単位の生データを保存する").

    Mirrors the JSON shape in docs/specs/...詳細設計書_v1.0.md §22, with
    declared_target/actual_target kept separate per §5.2.
    """

    session_id: str
    round_id: str
    round_number: int
    dart_index: int  # 1..3 within the round
    throw_number_in_session: int  # 1..24 overall
    detection_source: DetectionSource
    data_kind: DataKind = DataKind.MEASURED
    throw_id: str = field(default_factory=_new_id)
    score: int | None = None
    segment: str | None = None
    ring: Ring | None = None
    declared_target: str | None = None
    actual_target: str | None = None
    raw_x: float | None = None
    raw_y: float | None = None
    normalized_x: float | None = None
    normalized_y: float | None = None
    distance_from_bull: float | None = None
    coordinate_source: str | None = None
    confidence: float | None = None
    created_at: str = field(default_factory=_now_iso)

    def __post_init__(self) -> None:
        if not 1 <= self.dart_index <= 3:
            raise ValueError(f"dart_index must be 1..3, got {self.dart_index}")
        if not 1 <= self.throw_number_in_session <= 24:
            raise ValueError(
                f"throw_number_in_session must be 1..24, got {self.throw_number_in_session}"
            )
        require_confidence_for_estimate(self.data_kind, self.confidence)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["detection_source"] = self.detection_source.value
        data["data_kind"] = self.data_kind.value
        data["ring"] = self.ring.value if self.ring else None
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Throw":
        data = dict(data)
        data["detection_source"] = DetectionSource(data["detection_source"])
        data["data_kind"] = DataKind(data["data_kind"])
        if data.get("ring") is not None:
            data["ring"] = Ring(data["ring"])
        return cls(**data)


@dataclass
class PracticeSession:
    account_id: str
    player_id: str
    session_id: str = field(default_factory=_new_id)
    equipment_id: str | None = None
    game_type: GameType = GameType.COUNT_UP
    practice_type: str | None = None
    status: SessionStatus = SessionStatus.IN_PROGRESS
    started_at: str = field(default_factory=_now_iso)
    ended_at: str | None = None
    total_score: int | None = None
    created_at: str = field(default_factory=_now_iso)
    rounds: list[CountupRound] = field(default_factory=list)
    throws: list[Throw] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "account_id": self.account_id,
            "player_id": self.player_id,
            "equipment_id": self.equipment_id,
            "game_type": self.game_type.value,
            "practice_type": self.practice_type,
            "status": self.status.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "total_score": self.total_score,
            "created_at": self.created_at,
            "rounds": [r.to_dict() for r in self.rounds],
            "throws": [t.to_dict() for t in self.throws],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PracticeSession":
        data = dict(data)
        data["game_type"] = GameType(data["game_type"])
        data["status"] = SessionStatus(data["status"])
        rounds = [CountupRound.from_dict(r) for r in data.pop("rounds", [])]
        throws = [Throw.from_dict(t) for t in data.pop("throws", [])]
        return cls(rounds=rounds, throws=throws, **data)
