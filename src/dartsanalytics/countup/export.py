"""JSON export for a COUNT-UP session (docs §Phase1 completion item, §22).

Deliberately plain: json.dumps over dataclass-derived dicts, no schema
library dependency yet (AGENTS.md — zero dependencies until a later phase
genuinely needs one).
"""

from __future__ import annotations

import json
from pathlib import Path

from dartsanalytics.countup.session_result import summarize
from dartsanalytics.models.entities import PracticeSession


def export_session_json(session: PracticeSession, *, indent: int | None = 2) -> str:
    data = session.to_dict()
    data["result"] = summarize(session).to_dict()
    return json.dumps(data, ensure_ascii=False, indent=indent)


def write_session_json(session: PracticeSession, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(export_session_json(session), encoding="utf-8")
    return path
