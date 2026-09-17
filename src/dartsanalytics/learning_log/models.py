"""Personal learning log entities (docs §9).

docs §9, verbatim requirement: record intervention / before / change /
after / result / analysis-or-model version, and never conclude a causal
relationship from a single trial ("単一試行だけで因果関係を断定しない").

A LearningLogEntry always ties to a Phase 8 Experiment (experiment_id) —
the log doesn't duplicate the measured baseline/test metrics (those stay
in experiments/experiment_results, see db/schema/0001_initial.sql); it
adds the human-readable narrative (what was changed and why) plus the
algorithm/model version bookkeeping §9/§10 ask for, so a past result can
be reproduced or at least understood later even if the underlying
algorithm has since changed.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _new_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LearningLogEntry:
    experiment_id: str
    intervention_description: str  # what changed (e.g. "リリースタイミングを0.1秒遅らせる")
    before_summary: str  # human-readable state before the change
    change_description: str  # the change itself, in the player's own terms
    trial_number: int  # which attempt # of this same intervention_description (>= 1)
    model_versions: dict[str, str]  # e.g. {"pose": "pose_landmarker_v1", "board_calib": "board_calib_v1"}
    entry_id: str = field(default_factory=_new_id)
    after_summary: str | None = None  # filled in once the test phase is measured
    result_summary: str | None = None  # filled in once a Decision (continue/revert/retest) is made
    created_at: str = field(default_factory=_now_iso)

    def __post_init__(self) -> None:
        if self.trial_number < 1:
            raise ValueError(f"trial_number must be >= 1, got {self.trial_number}")
        if not self.model_versions:
            raise ValueError(
                "model_versions must not be empty — docs §9/§10 require the "
                "algorithm/model version to be recorded for reproducibility"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "experiment_id": self.experiment_id,
            "intervention_description": self.intervention_description,
            "before_summary": self.before_summary,
            "change_description": self.change_description,
            "after_summary": self.after_summary,
            "result_summary": self.result_summary,
            "model_versions": dict(self.model_versions),
            "trial_number": self.trial_number,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LearningLogEntry":
        return cls(**data)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "LearningLogEntry":
        data = dict(row)
        data["model_versions"] = json.loads(data.pop("model_versions_json"))
        return cls(**data)
