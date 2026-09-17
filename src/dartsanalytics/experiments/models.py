"""Experiment workflow state (docs §20, DB table `experiments`/
`experiment_results` §21).

Plain dataclass mirroring the `experiments` DB table (Phase 0 schema),
following the same to_dict()/from_dict() convention as
dartsanalytics.models.entities. No DB read/write code is added here —
consistent with every other analysis module in this codebase so far
(board/pose/grip/integrated are all pure computation over in-memory
objects; no repository/DAO layer exists yet in any Phase, so adding one
just for experiments would be scope creep beyond what this phase needs).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from dartsanalytics.experiments.decision import Decision


def _new_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


VALID_STATUSES = ("baseline", "testing", "decided")


@dataclass
class Experiment:
    intervention_id: str
    baseline_session_ids: list[str]
    experiment_id: str = field(default_factory=_new_id)
    test_session_ids: list[str] = field(default_factory=list)
    status: str = "baseline"  # matches the DB CHECK constraint: baseline | testing | decided
    decision: Decision | None = None
    created_at: str = field(default_factory=_now_iso)

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}, got {self.status!r}")
        if not self.baseline_session_ids:
            raise ValueError("baseline_session_ids must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "intervention_id": self.intervention_id,
            "baseline_session_ids": list(self.baseline_session_ids),
            "test_session_ids": list(self.test_session_ids),
            "status": self.status,
            "decision": self.decision.value if self.decision else None,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Experiment":
        data = dict(data)
        if data.get("decision"):
            data["decision"] = Decision(data["decision"])
        return cls(**data)
