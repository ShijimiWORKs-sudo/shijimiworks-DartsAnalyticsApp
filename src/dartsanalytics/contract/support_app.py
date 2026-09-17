"""DartsSupportApp JSON contract (docs §Phase10, §2 「既存アプリとの
位置付け」).

docs §Phase10, verbatim minimum field list:
account_id / player_id / practice_menu_id / game_session_id / record_id /
timestamp / game_type / practice_type / BULL/DOUBLE/TRIPLE /
throw coordinates / sync state / analysis version

**IMPORTANT — unverified against the real DartsSupportApp** (see
docs/codex/reports/status.md 未解決事項3): this session requested
read-only access to the sibling `DartsApp`/`DartsSupportApp` folders
(docs §1「既存プロジェクトの設計思想を確認するため」) specifically to
cross-check field names/types against DartsSupportApp's actual contract
implementation, and that request went unanswered/timed out. This module
therefore implements exactly the minimal field list docs §Phase10 states,
verbatim, and nothing beyond it — it has **not** been validated against
DartsSupportApp's real JSON schema (field names, casing, nesting, or
transport). Treat every field name here as "per the spec document", not
as "confirmed compatible with the existing app", until that cross-check
happens (flagged again in docs/codex/reports/phase10_notes.md and
status.md's 未解決事項).

Design notes on fields not already 1:1 with dartsanalytics.models.entities:

- `practice_menu_id`: no internal concept of a "practice menu" exists in
  this app (COUNT-UP is the only game type, docs 設計原則 #1) — this is
  presumably assigned by DartsSupportApp's own practice-management
  system, so it's accepted as an optional caller-supplied value, not
  derived from anything here.
- `game_session_id` / `record_id`: docs' names for what this app calls
  `session_id` / `throw_id` internally (dartsanalytics.models.entities).
  Renamed only in this contract layer, not in the internal models — the
  internal models keep their own names (AGENTS.md "最小変更": don't
  rename existing fields just to match an unverified external contract).
- `BULL/DOUBLE/TRIPLE`: docs names only 3 ring values, but this app's
  own `Ring` enum (dartsanalytics.common.enums) already includes SINGLE,
  DBULL, and MISS too (docs §5.1/§22 use DBULL themselves) — a strict
  superset. Passed through as Ring's own string value rather than
  lossily collapsing to the 3 named categories.
- `sync_state`: new concept (dartsanalytics.common.enums.SyncState),
  since no throw previously needed to track "has this been sent to
  DartsSupportApp yet". Defaults to PENDING.
- `analysis_version`: caller-supplied (AGENTS.md "解析アルゴリズムには
  バージョン文字列を付ける"). Defaults to DEFAULT_ANALYSIS_VERSION for a
  throw with no analysis algorithm behind it (a MEASURED throw straight
  from DARTSLIVE HOME has no "algorithm version" of its own).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dartsanalytics.common.enums import SyncState
from dartsanalytics.models.entities import PracticeSession, Throw

DEFAULT_ANALYSIS_VERSION = "raw_measurement_v1"


@dataclass(frozen=True)
class SupportAppThrowRecord:
    account_id: str
    player_id: str
    game_session_id: str
    record_id: str
    timestamp: str
    game_type: str
    practice_type: str | None
    ring: str | None  # BULL/DOUBLE/TRIPLE/SINGLE/DBULL/MISS — see module docstring
    normalized_x: float | None
    normalized_y: float | None
    distance_from_bull: float | None
    sync_state: str
    analysis_version: str
    practice_menu_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "player_id": self.player_id,
            "practice_menu_id": self.practice_menu_id,
            "game_session_id": self.game_session_id,
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "game_type": self.game_type,
            "practice_type": self.practice_type,
            "ring": self.ring,
            "normalized_x": self.normalized_x,
            "normalized_y": self.normalized_y,
            "distance_from_bull": self.distance_from_bull,
            "sync_state": self.sync_state,
            "analysis_version": self.analysis_version,
        }


def build_support_app_record(
    session: PracticeSession,
    throw: Throw,
    *,
    practice_menu_id: str | None = None,
    sync_state: SyncState = SyncState.PENDING,
    analysis_version: str = DEFAULT_ANALYSIS_VERSION,
) -> SupportAppThrowRecord:
    if throw.session_id != session.session_id:
        raise ValueError(
            f"throw.session_id ({throw.session_id!r}) does not match session.session_id ({session.session_id!r})"
        )

    distance = throw.distance_from_bull
    if distance is None and throw.normalized_x is not None and throw.normalized_y is not None:
        distance = math.hypot(throw.normalized_x, throw.normalized_y)

    return SupportAppThrowRecord(
        account_id=session.account_id,
        player_id=session.player_id,
        game_session_id=session.session_id,
        record_id=throw.throw_id,
        timestamp=throw.created_at,
        game_type=session.game_type.value,
        practice_type=session.practice_type,
        ring=throw.ring.value if throw.ring is not None else None,
        normalized_x=throw.normalized_x,
        normalized_y=throw.normalized_y,
        distance_from_bull=distance,
        sync_state=sync_state.value,
        analysis_version=analysis_version,
        practice_menu_id=practice_menu_id,
    )


def build_support_app_records(
    session: PracticeSession,
    *,
    practice_menu_id: str | None = None,
    sync_state: SyncState = SyncState.PENDING,
    analysis_version: str = DEFAULT_ANALYSIS_VERSION,
) -> list[SupportAppThrowRecord]:
    return [
        build_support_app_record(
            session,
            t,
            practice_menu_id=practice_menu_id,
            sync_state=sync_state,
            analysis_version=analysis_version,
        )
        for t in session.throws
    ]


def export_support_app_json(
    session: PracticeSession,
    *,
    practice_menu_id: str | None = None,
    sync_state: SyncState = SyncState.PENDING,
    analysis_version: str = DEFAULT_ANALYSIS_VERSION,
    indent: int | None = 2,
) -> str:
    records = build_support_app_records(
        session, practice_menu_id=practice_menu_id, sync_state=sync_state, analysis_version=analysis_version
    )
    return json.dumps([r.to_dict() for r in records], ensure_ascii=False, indent=indent)


def write_support_app_json(session: PracticeSession, path: str | Path, **kwargs: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(export_support_app_json(session, **kwargs), encoding="utf-8")
    return path
