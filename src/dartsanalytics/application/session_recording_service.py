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

import json
from dataclasses import dataclass
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
from dartsanalytics.pose.features import PoseFeatures
from dartsanalytics.pose.multi_angle import MultiAngleMergeResult, merge_multi_angle_pose_features
from dartsanalytics.video.angles import ShootingAngle
from dartsanalytics.video.models import MediaAsset

DEFAULT_POSE_ALGORITHM_VERSION = "pose_landmarker_v1"
MULTI_ANGLE_MERGE_ALGORITHM_VERSION = "multi_angle_merge_v1"


@dataclass(frozen=True)
class MultiAngleRecordingResult:
    """What `record_multi_angle_pose_analysis` actually wrote, so a caller
    can trace the merged result back to its per-angle sources (or re-fetch
    them) without re-deriving anything."""

    per_angle_run_ids: dict[ShootingAngle, str]
    merged_report_id: str
    merge_result: MultiAngleMergeResult


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

    def record_pose_features(
        self,
        media_id: str,
        features: PoseFeatures,
        *,
        algorithm_version: str = DEFAULT_POSE_ALGORITHM_VERSION,
        throw_id: str | None = None,
    ) -> str:
        """Persists a single video's (single-angle) Phase 5 pose features —
        the write path `record_multi_angle_pose_analysis` below also uses,
        once per contributing angle, so each angle's raw estimate stays
        individually queryable/traceable even after merging (see that
        method's docstring for why nothing is discarded)."""
        with SqliteUnitOfWork(self._db_path) as uow:
            run_id = uow.pose_features.save_run(media_id, algorithm_version, status="complete")
            uow.pose_features.save_features(run_id, features, throw_id=throw_id)
            return run_id

    def record_multi_angle_pose_analysis(
        self,
        session_id: str,
        media_ids_by_angle: dict[ShootingAngle, str],
        features_by_angle: dict[ShootingAngle, PoseFeatures],
        *,
        algorithm_version: str = DEFAULT_POSE_ALGORITHM_VERSION,
        throw_id: str | None = None,
    ) -> MultiAngleRecordingResult:
        """Wires dartsanalytics.pose.multi_angle (§6, 4-angle feature
        integration) into the DB layer (release-readiness.md 未解決事項9).

        Two things get written, in one transaction:

        1. Each angle's OWN `PoseFeatures`, via the same per-run mechanism
           `record_pose_features` uses (one `video_analysis_runs` row per
           angle's `media_id`, matching how single-angle recording already
           works) — so a per-angle estimate is never lost or only
           reachable through the merge. `media_ids_by_angle` must already
           be recorded media (record_media_asset) for every angle present
           in `features_by_angle`; angles with a media_id but no features
           entry are skipped (mirrors `merge_multi_angle_pose_features`'s
           own tolerance for partial angle coverage).
        2. The full `MultiAngleMergeResult` (chosen value per feature,
           `source_angle`, `contributing_angles`, `disagreement_deg`) as
           one `analysis_reports` row tied to `session_id` — reusing the
           existing generic `save_report` path (same one Phase 9's
           AdvisorOutput uses) rather than adding a new table, since the
           merge result is already a self-describing JSON-serializable
           report and nothing here needs it to be queried column-by-column.
           `MultiAngleMergeResult.to_dict()`'s `merged` values collapse
           each feature to its chosen `value`/`confidence`/`data_kind` plus
           full provenance — deliberately NOT written into the plain
           `pose_features` table as a 6th "virtual" run, since that table
           has no `media_id` a merged (multi-source) value could honestly
           point at.

        Raises ValueError if `features_by_angle` is empty (same guard
        `merge_multi_angle_pose_features` enforces) or if any angle in
        `features_by_angle` has no corresponding entry in
        `media_ids_by_angle` (can't record features against media that was
        never registered).
        """
        if not features_by_angle:
            raise ValueError("features_by_angle must not be empty")
        missing_media = [a for a in features_by_angle if a not in media_ids_by_angle]
        if missing_media:
            raise ValueError(
                f"media_ids_by_angle is missing an entry for angle(s): {[a.value for a in missing_media]}"
            )

        merge_result = merge_multi_angle_pose_features(features_by_angle)

        with SqliteUnitOfWork(self._db_path) as uow:
            per_angle_run_ids: dict[ShootingAngle, str] = {}
            for angle, features in features_by_angle.items():
                run_id = uow.pose_features.save_run(
                    media_ids_by_angle[angle], algorithm_version, status="complete"
                )
                uow.pose_features.save_features(run_id, features, throw_id=throw_id)
                per_angle_run_ids[angle] = run_id

            merged_report_id = uow.analysis_reports.save_report(
                session_id, json.dumps(merge_result.to_dict(), ensure_ascii=False)
            )

        return MultiAngleRecordingResult(
            per_angle_run_ids=per_angle_run_ids,
            merged_report_id=merged_report_id,
            merge_result=merge_result,
        )

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
