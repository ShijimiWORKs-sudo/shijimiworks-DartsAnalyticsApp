"""SessionRecordingService — the reference Application Service for the
repository layer (docs §10 resolution).

Demonstrates the intended call shape (``UI -> Application Service ->
Repository Interface -> Local DB Repository``) for the write paths every
later phase's UI would actually need: recording a finished COUNT-UP
session, attaching board calibration / media / grip results to it, saving
an AI advisor report, and recording an experiment's baseline/test
decision. Each method opens exactly one SqliteUnitOfWork and commits once
(or not at all, on error) — callers never see a partial write.

This is intentionally not a full "app backend" — no auth, no HTTP layer —
this project has no UI yet (docs' own release-unresolved list already
flags "DB persistence" as separate from "UI"). What this proves is that
the DB layer is *usable* from outside dartsanalytics.db, with the
transaction boundary in the right place.
"""

from __future__ import annotations

from pathlib import Path

from dartsanalytics.advisor.models import AdvisorOutput
from dartsanalytics.board.calibration import BoardCalibration
from dartsanalytics.db.connection import DEFAULT_DB_PATH
from dartsanalytics.db.unit_of_work import SqliteUnitOfWork
from dartsanalytics.experiments.comparison import ExperimentComparison
from dartsanalytics.experiments.models import Experiment
from dartsanalytics.grip.analysis import GripAnalysisResult
from dartsanalytics.learning_log.analysis import InterventionHistory, summarize_intervention_history
from dartsanalytics.learning_log.models import LearningLogEntry
from dartsanalytics.models.entities import Account, Player, PracticeSession
from dartsanalytics.video.models import MediaAsset


class SessionRecordingService:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path

    def ensure_account_and_player(self, account: Account, player: Player) -> None:
        """Idempotent (INSERT OR REPLACE underneath) — safe to call every
        app launch before recording a session."""
        with SqliteUnitOfWork(self._db_path) as uow:
            uow.accounts.save(account)
            uow.players.save(player)

    def record_countup_session(self, session: PracticeSession) -> None:
        """Persists a finished (or in-progress) COUNT-UP session with all
        its rounds and throws atomically — either the whole session lands
        on disk or none of it does (see SqliteSessionRepository /
        SqliteUnitOfWork docstrings for how the rollback-on-error
        guarantee is implemented)."""
        with SqliteUnitOfWork(self._db_path) as uow:
            uow.sessions.save_session(session)

    def get_session_history(self, player_id: str) -> list[PracticeSession]:
        with SqliteUnitOfWork(self._db_path) as uow:
            return uow.sessions.list_sessions_by_player(player_id)

    def record_board_calibration(
        self, calibration: BoardCalibration, *, session_id: str | None = None
    ) -> str:
        with SqliteUnitOfWork(self._db_path) as uow:
            return uow.calibrations.save(calibration, session_id=session_id)

    def record_media_asset(self, asset: MediaAsset) -> None:
        with SqliteUnitOfWork(self._db_path) as uow:
            uow.media.save(asset)

    def record_grip_analysis(
        self, media_id: str, result: GripAnalysisResult, algorithm_version: str
    ) -> str:
        with SqliteUnitOfWork(self._db_path) as uow:
            return uow.grip_runs.save(media_id, result, algorithm_version)

    def record_advisor_output(self, advisor_output: AdvisorOutput) -> str:
        with SqliteUnitOfWork(self._db_path) as uow:
            return uow.analysis_reports.save_advisor_output(
                advisor_output.session_id, advisor_output
            )

    def record_experiment(self, experiment: Experiment) -> None:
        with SqliteUnitOfWork(self._db_path) as uow:
            uow.experiments.save(experiment)

    def record_experiment_decision(
        self, experiment: Experiment, comparison: ExperimentComparison
    ) -> None:
        """Saves the Experiment row (with its final ``decision``) and its
        per-metric results together — one commit, matching how docs §20's
        Baseline/Test/比較/決定 flow is meant to land in the DB as a single
        decided-experiment record, not two independent writes that could
        disagree if one failed."""
        with SqliteUnitOfWork(self._db_path) as uow:
            uow.experiments.save(experiment)
            uow.experiments.save_results(experiment.experiment_id, comparison)

    def record_learning_log_entry(
        self,
        *,
        experiment_id: str,
        intervention_description: str,
        before_summary: str,
        change_description: str,
        model_versions: dict[str, str],
        after_summary: str | None = None,
        result_summary: str | None = None,
    ) -> LearningLogEntry:
        """Records one trial of an intervention (§9). trial_number is
        assigned automatically from how many times this exact
        intervention_description has been logged before, so the caller
        never has to track — or risk miscounting — that itself."""
        with SqliteUnitOfWork(self._db_path) as uow:
            trial_number = uow.learning_log.next_trial_number(intervention_description)
            entry = LearningLogEntry(
                experiment_id=experiment_id,
                intervention_description=intervention_description,
                before_summary=before_summary,
                change_description=change_description,
                trial_number=trial_number,
                model_versions=model_versions,
                after_summary=after_summary,
                result_summary=result_summary,
            )
            uow.learning_log.save_entry(entry)
            return entry

    def update_learning_log_entry_outcome(
        self, entry_id: str, *, after_summary: str, result_summary: str
    ) -> None:
        """Fills in after/result once the test phase has been measured —
        an entry is normally created at intervention time (before/change
        known, after/result not yet) and updated once the experiment is
        decided."""
        with SqliteUnitOfWork(self._db_path) as uow:
            entry = uow.learning_log.get_entry(entry_id)
            if entry is None:
                raise ValueError(f"no learning log entry with id {entry_id!r}")
            entry.after_summary = after_summary
            entry.result_summary = result_summary
            uow.learning_log.save_entry(entry)

    def get_intervention_history(self, intervention_description: str) -> InterventionHistory:
        """Returns every trial of this intervention plus the mandatory
        causal-confidence caution (see
        dartsanalytics.learning_log.analysis.causal_confidence_note) — a
        UI should always show this caution alongside the trial list, never
        just the latest result."""
        with SqliteUnitOfWork(self._db_path) as uow:
            entries = uow.learning_log.list_entries_by_intervention(intervention_description)
        if not entries:
            raise ValueError(f"no learning log entries for {intervention_description!r}")
        return summarize_intervention_history(entries)
