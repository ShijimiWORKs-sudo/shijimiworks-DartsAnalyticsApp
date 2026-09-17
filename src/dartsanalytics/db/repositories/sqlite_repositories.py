"""Local DB Repository tier (docs §10 resolution) — SQLite implementation.

Every class here takes an open ``sqlite3.Connection`` and issues plain SQL
against the 0001_initial.sql schema. None of them call ``commit()`` or
``rollback()`` themselves — that is the UnitOfWork's job
(dartsanalytics.db.unit_of_work), so several repositories can share one
atomic transaction (e.g. "a session's rows and its throw rows commit or
roll back together").

Design notes:
  * Existing-vs-new is resolved with ``INSERT OR REPLACE`` keyed on the
    dataclass's own id field — repositories are idempotent upserts, not
    append-only logs, matching how PracticeSession/Throw/etc. are already
    mutated in place elsewhere in this codebase (e.g. a session's
    ``status``/``ended_at``/``total_score`` change as it completes).
  * Reads reconstruct the exact dataclasses defined in
    dartsanalytics.models.entities / board.calibration / video.models /
    experiments.models — the DB layer never invents a parallel "row" type.
  * SQLite's own CHECK/FOREIGN KEY constraints (already declared in the
    schema) are the corruption/invalid-data guard; these repositories do
    not re-validate — a bad value should surface as sqlite3.IntegrityError,
    not be silently coerced. This is deliberate: the schema is the single
    source of truth for what "valid" means, so a corrupt/inconsistent
    write is caught here rather than propagating downstream.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from dartsanalytics.advisor.models import AdvisorOutput
from dartsanalytics.board.calibration import BoardCalibration
from dartsanalytics.common.enums import DataKind, DetectionSource, GameType, Ring, SessionStatus
from dartsanalytics.experiments.comparison import ExperimentComparison
from dartsanalytics.experiments.decision import Decision
from dartsanalytics.experiments.models import Experiment
from dartsanalytics.grip.analysis import GripAnalysisResult
from dartsanalytics.learning_log.models import LearningLogEntry
from dartsanalytics.models.entities import (
    Account,
    CountupRound,
    EquipmentProfile,
    Player,
    PracticeSession,
    Throw,
)
from dartsanalytics.pose.features import PoseFeatures
from dartsanalytics.video.models import MediaAsset


def _new_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteAccountRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, account: Account) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO accounts (account_id, display_name, created_at) "
            "VALUES (?, ?, ?)",
            (account.account_id, account.display_name, account.created_at),
        )

    def get(self, account_id: str) -> Account | None:
        row = self._conn.execute(
            "SELECT * FROM accounts WHERE account_id = ?", (account_id,)
        ).fetchone()
        return Account(**dict(row)) if row else None

    def list_all(self) -> list[Account]:
        rows = self._conn.execute("SELECT * FROM accounts ORDER BY created_at").fetchall()
        return [Account(**dict(r)) for r in rows]


class SqlitePlayerRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, player: Player) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO players "
            "(player_id, account_id, display_name, dominant_hand, dominant_eye, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                player.player_id,
                player.account_id,
                player.display_name,
                player.dominant_hand,
                player.dominant_eye,
                player.created_at,
            ),
        )

    def get(self, player_id: str) -> Player | None:
        row = self._conn.execute(
            "SELECT * FROM players WHERE player_id = ?", (player_id,)
        ).fetchone()
        return Player(**dict(row)) if row else None

    def list_by_account(self, account_id: str) -> list[Player]:
        rows = self._conn.execute(
            "SELECT * FROM players WHERE account_id = ? ORDER BY created_at", (account_id,)
        ).fetchall()
        return [Player(**dict(r)) for r in rows]


class SqliteEquipmentRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, profile: EquipmentProfile) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO equipment_profiles "
            "(equipment_id, player_id, barrel_maker, barrel_name, barrel_weight_g, "
            "total_weight_g, flight_type, shaft_type, shaft_length, tip_type, "
            "changed_at, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                profile.equipment_id,
                profile.player_id,
                profile.barrel_maker,
                profile.barrel_name,
                profile.barrel_weight_g,
                profile.total_weight_g,
                profile.flight_type,
                profile.shaft_type,
                profile.shaft_length,
                profile.tip_type,
                profile.changed_at,
                profile.notes,
            ),
        )

    def get(self, equipment_id: str) -> EquipmentProfile | None:
        row = self._conn.execute(
            "SELECT * FROM equipment_profiles WHERE equipment_id = ?", (equipment_id,)
        ).fetchone()
        return EquipmentProfile(**dict(row)) if row else None

    def list_by_player(self, player_id: str) -> list[EquipmentProfile]:
        rows = self._conn.execute(
            "SELECT * FROM equipment_profiles WHERE player_id = ? ORDER BY changed_at",
            (player_id,),
        ).fetchall()
        return [EquipmentProfile(**dict(r)) for r in rows]


class SqliteSessionRepository:
    """Persists PracticeSession + its CountupRounds + Throws (+ optional
    throw_coordinates) as one unit. Callers should wrap this in a
    UnitOfWork transaction — see module docstring."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_session(self, session: PracticeSession) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO practice_sessions "
            "(session_id, account_id, player_id, equipment_id, game_type, practice_type, "
            "status, started_at, ended_at, total_score, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session.session_id,
                session.account_id,
                session.player_id,
                session.equipment_id,
                session.game_type.value,
                session.practice_type,
                session.status.value,
                session.started_at,
                session.ended_at,
                session.total_score,
                session.created_at,
            ),
        )
        for round_ in session.rounds:
            self._save_round(round_)
        for throw in session.throws:
            self._save_throw(throw)

    def _save_round(self, round_: CountupRound) -> None:
        # ON CONFLICT(round_id) — not "INSERT OR REPLACE" — deliberately: a
        # plain REPLACE resolves ANY unique-constraint conflict (including
        # the UNIQUE(session_id, round_number) index) by silently deleting
        # the pre-existing row, which would let a caller overwrite a
        # different round's row by accident with no error. Upserting only
        # on the primary key keeps re-saving the same round_id idempotent
        # while still surfacing a genuine round_number collision as
        # sqlite3.IntegrityError (see test_repositories.py).
        self._conn.execute(
            "INSERT INTO countup_rounds (round_id, session_id, round_number, round_score) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(round_id) DO UPDATE SET "
            "session_id=excluded.session_id, round_number=excluded.round_number, "
            "round_score=excluded.round_score",
            (round_.round_id, round_.session_id, round_.round_number, round_.round_score),
        )

    def _save_throw(self, throw: Throw) -> None:
        # Same ON CONFLICT(throw_id)-only upsert reasoning as _save_round
        # above, guarding throws.UNIQUE(session_id, throw_number_in_session)
        # against being silently bypassed by "INSERT OR REPLACE".
        self._conn.execute(
            "INSERT INTO throws "
            "(throw_id, session_id, round_id, round_number, dart_index, "
            "throw_number_in_session, score, segment, ring, declared_target, "
            "actual_target, detection_source, data_kind, confidence, raw_event_json, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(throw_id) DO UPDATE SET "
            "session_id=excluded.session_id, round_id=excluded.round_id, "
            "round_number=excluded.round_number, dart_index=excluded.dart_index, "
            "throw_number_in_session=excluded.throw_number_in_session, "
            "score=excluded.score, segment=excluded.segment, ring=excluded.ring, "
            "declared_target=excluded.declared_target, actual_target=excluded.actual_target, "
            "detection_source=excluded.detection_source, data_kind=excluded.data_kind, "
            "confidence=excluded.confidence, raw_event_json=excluded.raw_event_json",
            (
                throw.throw_id,
                throw.session_id,
                throw.round_id,
                throw.round_number,
                throw.dart_index,
                throw.throw_number_in_session,
                throw.score,
                throw.segment,
                throw.ring.value if throw.ring else None,
                throw.declared_target,
                throw.actual_target,
                throw.detection_source.value,
                throw.data_kind.value,
                throw.confidence,
                None,
                throw.created_at,
            ),
        )
        if throw.raw_x is not None or throw.normalized_x is not None:
            self._conn.execute(
                "INSERT OR REPLACE INTO throw_coordinates "
                "(throw_id, raw_x, raw_y, normalized_x, normalized_y, distance_from_bull, "
                "angle, detected_segment, detection_confidence, coordinate_source, "
                "calibration_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    throw.throw_id,
                    throw.raw_x,
                    throw.raw_y,
                    throw.normalized_x,
                    throw.normalized_y,
                    throw.distance_from_bull,
                    None,
                    throw.segment,
                    throw.confidence,
                    throw.coordinate_source,
                    None,
                ),
            )

    def get_session(self, session_id: str) -> PracticeSession | None:
        row = self._conn.execute(
            "SELECT * FROM practice_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        rounds = [
            CountupRound(
                round_id=r["round_id"],
                session_id=r["session_id"],
                round_number=r["round_number"],
                round_score=r["round_score"],
            )
            for r in self._conn.execute(
                "SELECT * FROM countup_rounds WHERE session_id = ? ORDER BY round_number",
                (session_id,),
            ).fetchall()
        ]
        throws = [self._row_to_throw(r) for r in self._conn.execute(
            "SELECT * FROM throws WHERE session_id = ? ORDER BY throw_number_in_session",
            (session_id,),
        ).fetchall()]
        return PracticeSession(
            session_id=data["session_id"],
            account_id=data["account_id"],
            player_id=data["player_id"],
            equipment_id=data["equipment_id"],
            game_type=GameType(data["game_type"]),
            practice_type=data["practice_type"],
            status=SessionStatus(data["status"]),
            started_at=data["started_at"],
            ended_at=data["ended_at"],
            total_score=data["total_score"],
            created_at=data["created_at"],
            rounds=rounds,
            throws=throws,
        )

    def _row_to_throw(self, row: sqlite3.Row) -> Throw:
        data = dict(row)
        coord_row = self._conn.execute(
            "SELECT * FROM throw_coordinates WHERE throw_id = ?", (data["throw_id"],)
        ).fetchone()
        coord = dict(coord_row) if coord_row else {}
        return Throw(
            throw_id=data["throw_id"],
            session_id=data["session_id"],
            round_id=data["round_id"],
            round_number=data["round_number"],
            dart_index=data["dart_index"],
            throw_number_in_session=data["throw_number_in_session"],
            detection_source=DetectionSource(data["detection_source"]),
            data_kind=DataKind(data["data_kind"]),
            score=data["score"],
            segment=data["segment"],
            ring=Ring(data["ring"]) if data["ring"] else None,
            declared_target=data["declared_target"],
            actual_target=data["actual_target"],
            raw_x=coord.get("raw_x"),
            raw_y=coord.get("raw_y"),
            normalized_x=coord.get("normalized_x"),
            normalized_y=coord.get("normalized_y"),
            distance_from_bull=coord.get("distance_from_bull"),
            coordinate_source=coord.get("coordinate_source"),
            confidence=data["confidence"],
            created_at=data["created_at"],
        )

    def list_sessions_by_player(self, player_id: str) -> list[PracticeSession]:
        rows = self._conn.execute(
            "SELECT session_id FROM practice_sessions WHERE player_id = ? "
            "ORDER BY started_at",
            (player_id,),
        ).fetchall()
        sessions = [self.get_session(r["session_id"]) for r in rows]
        return [s for s in sessions if s is not None]


class SqliteCalibrationRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, calibration: BoardCalibration, *, session_id: str | None = None) -> str:
        calibration_id = _new_id()
        self._conn.execute(
            "INSERT INTO board_calibrations "
            "(calibration_id, session_id, center_x_px, center_y_px, radius_px, "
            "algorithm_version, confidence, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                calibration_id,
                session_id,
                calibration.center_x_px,
                calibration.center_y_px,
                calibration.radius_px,
                calibration.algorithm_version,
                calibration.confidence,
                _now_iso(),
            ),
        )
        return calibration_id

    def get(self, calibration_id: str) -> tuple[BoardCalibration, str | None] | None:
        row = self._conn.execute(
            "SELECT * FROM board_calibrations WHERE calibration_id = ?", (calibration_id,)
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        calibration = BoardCalibration(
            center_x_px=data["center_x_px"],
            center_y_px=data["center_y_px"],
            radius_px=data["radius_px"],
            algorithm_version=data["algorithm_version"],
            confidence=data["confidence"],
        )
        return calibration, data["session_id"]


class SqliteMediaRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, asset: MediaAsset) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO media_assets "
            "(media_id, session_id, media_type, angle, file_path, checksum, "
            "quality_grade, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                asset.media_id,
                asset.session_id,
                asset.media_type,
                asset.angle.value if asset.angle else None,
                asset.file_path,
                asset.checksum,
                asset.quality_grade,
                asset.created_at,
            ),
        )

    def get(self, media_id: str) -> MediaAsset | None:
        row = self._conn.execute(
            "SELECT * FROM media_assets WHERE media_id = ?", (media_id,)
        ).fetchone()
        return MediaAsset.from_dict(dict(row)) if row else None

    def list_by_session(self, session_id: str) -> list[MediaAsset]:
        rows = self._conn.execute(
            "SELECT * FROM media_assets WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
        return [MediaAsset.from_dict(dict(r)) for r in rows]


class SqlitePoseFeatureRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_run(self, media_id: str, algorithm_version: str, status: str) -> str:
        run_id = _new_id()
        self._conn.execute(
            "INSERT INTO video_analysis_runs "
            "(run_id, media_id, algorithm_version, status, started_at, finished_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, media_id, algorithm_version, status, _now_iso(), None),
        )
        return run_id

    def save_features(
        self, run_id: str, features: PoseFeatures, *, throw_id: str | None = None
    ) -> None:
        for name, value in (
            ("body_tilt_deg", features.body_tilt_deg),
            ("shoulder_tilt_deg", features.shoulder_tilt_deg),
            ("hip_tilt_deg", features.hip_tilt_deg),
            ("left_elbow_angle_deg", features.left_elbow_angle_deg),
            ("right_elbow_angle_deg", features.right_elbow_angle_deg),
        ):
            if value is None:
                continue
            self._conn.execute(
                "INSERT INTO pose_features "
                "(pose_feature_id, run_id, throw_id, feature_name, feature_value, "
                "data_kind, confidence) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    _new_id(),
                    run_id,
                    throw_id,
                    name,
                    value.value,
                    value.data_kind.value,
                    value.confidence,
                ),
            )

    def list_features_by_run(self, run_id: str) -> dict[str, dict]:
        rows = self._conn.execute(
            "SELECT * FROM pose_features WHERE run_id = ?", (run_id,)
        ).fetchall()
        return {
            r["feature_name"]: {
                "value": r["feature_value"],
                "confidence": r["confidence"],
                "data_kind": r["data_kind"],
            }
            for r in rows
        }


class SqliteGripAnalysisRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, media_id: str, result: GripAnalysisResult, algorithm_version: str) -> str:
        grip_run_id = _new_id()
        confidence = None
        if result.dominant.features is not None:
            confidence = result.dominant.features.wrist_angle_deg.confidence \
                if result.dominant.features.wrist_angle_deg else None
        self._conn.execute(
            "INSERT INTO grip_analysis_runs "
            "(grip_run_id, media_id, algorithm_version, result_json, confidence, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                grip_run_id,
                media_id,
                algorithm_version,
                json.dumps(result.to_dict()),
                confidence,
                _now_iso(),
            ),
        )
        return grip_run_id

    def get(self, grip_run_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM grip_analysis_runs WHERE grip_run_id = ?", (grip_run_id,)
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["result"] = json.loads(data["result_json"]) if data["result_json"] else None
        return data


class SqliteAnalysisReportRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_report(self, session_id: str, report_json: str) -> str:
        report_id = _new_id()
        self._conn.execute(
            "INSERT INTO analysis_reports (report_id, session_id, report_json, created_at) "
            "VALUES (?, ?, ?, ?)",
            (report_id, session_id, report_json, _now_iso()),
        )
        return report_id

    def save_hypothesis(self, report_id: str, description: str, confidence: float) -> str:
        hypothesis_id = _new_id()
        self._conn.execute(
            "INSERT INTO hypotheses (hypothesis_id, report_id, description, confidence, "
            "created_at) VALUES (?, ?, ?, ?, ?)",
            (hypothesis_id, report_id, description, confidence, _now_iso()),
        )
        return hypothesis_id

    def save_intervention(self, hypothesis_id: str | None, description: str) -> str:
        intervention_id = _new_id()
        self._conn.execute(
            "INSERT INTO interventions (intervention_id, hypothesis_id, description, "
            "created_at) VALUES (?, ?, ?, ?)",
            (intervention_id, hypothesis_id, description, _now_iso()),
        )
        return intervention_id

    def save_advisor_output(self, session_id: str, advisor_output: AdvisorOutput) -> str:
        """Persists a Phase 9 AdvisorOutput as one analysis_report (full
        JSON, observations/hypotheses/recommended_tests/caveats kept
        together) plus one hypotheses row per Hypothesis, so cause
        candidates stay queryable without re-parsing the report JSON."""
        report_id = self.save_report(session_id, json.dumps(advisor_output.to_dict()))
        for hypothesis in advisor_output.hypotheses:
            self.save_hypothesis(report_id, hypothesis.description, hypothesis.confidence)
        return report_id


class SqliteExperimentRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, experiment: Experiment) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO experiments "
            "(experiment_id, intervention_id, baseline_session_ids, test_session_ids, "
            "status, decision, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                experiment.experiment_id,
                experiment.intervention_id,
                json.dumps(experiment.baseline_session_ids),
                json.dumps(experiment.test_session_ids) if experiment.test_session_ids else None,
                experiment.status,
                experiment.decision.value if experiment.decision else None,
                experiment.created_at,
            ),
        )

    def get(self, experiment_id: str) -> Experiment | None:
        row = self._conn.execute(
            "SELECT * FROM experiments WHERE experiment_id = ?", (experiment_id,)
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        return Experiment(
            experiment_id=data["experiment_id"],
            intervention_id=data["intervention_id"],
            baseline_session_ids=json.loads(data["baseline_session_ids"]),
            test_session_ids=json.loads(data["test_session_ids"]) if data["test_session_ids"] else [],
            status=data["status"],
            decision=Decision(data["decision"]) if data["decision"] else None,
            created_at=data["created_at"],
        )

    def save_results(self, experiment_id: str, comparison: ExperimentComparison) -> None:
        for metric in comparison.metrics:
            self._conn.execute(
                "INSERT INTO experiment_results "
                "(experiment_result_id, experiment_id, metric_name, baseline_value, "
                "test_value, delta) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    _new_id(),
                    experiment_id,
                    metric.metric_name,
                    metric.baseline_value,
                    metric.test_value,
                    metric.delta,
                ),
            )

    def list_results(self, experiment_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM experiment_results WHERE experiment_id = ?", (experiment_id,)
        ).fetchall()
        return [dict(r) for r in rows]


class SqliteLearningLogRepository:
    """§9. Requires migration 0002_learning_log.sql to have been applied
    (SqliteUnitOfWork always runs apply_migrations() on connect, so any
    caller going through the UnitOfWork gets this automatically)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_entry(self, entry: LearningLogEntry) -> None:
        self._conn.execute(
            "INSERT INTO learning_log_entries "
            "(entry_id, experiment_id, intervention_description, before_summary, "
            "change_description, after_summary, result_summary, model_versions_json, "
            "trial_number, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(entry_id) DO UPDATE SET "
            "after_summary=excluded.after_summary, result_summary=excluded.result_summary",
            (
                entry.entry_id,
                entry.experiment_id,
                entry.intervention_description,
                entry.before_summary,
                entry.change_description,
                entry.after_summary,
                entry.result_summary,
                json.dumps(entry.model_versions),
                entry.trial_number,
                entry.created_at,
            ),
        )

    def get_entry(self, entry_id: str) -> LearningLogEntry | None:
        row = self._conn.execute(
            "SELECT * FROM learning_log_entries WHERE entry_id = ?", (entry_id,)
        ).fetchone()
        return LearningLogEntry.from_row(dict(row)) if row else None

    def list_entries_by_intervention(self, intervention_description: str) -> list[LearningLogEntry]:
        rows = self._conn.execute(
            "SELECT * FROM learning_log_entries WHERE intervention_description = ? "
            "ORDER BY trial_number",
            (intervention_description,),
        ).fetchall()
        return [LearningLogEntry.from_row(dict(r)) for r in rows]

    def list_all_entries(self) -> list[LearningLogEntry]:
        rows = self._conn.execute(
            "SELECT * FROM learning_log_entries ORDER BY created_at"
        ).fetchall()
        return [LearningLogEntry.from_row(dict(r)) for r in rows]

    def next_trial_number(self, intervention_description: str) -> int:
        """1 for a never-before-seen intervention_description, otherwise
        one past the highest trial_number already recorded for it — so
        callers don't have to track trial counts themselves and can't
        accidentally reuse a number (which would corrupt the "how many
        times has this actually been tried" count §9's caution logic
        depends on)."""
        row = self._conn.execute(
            "SELECT MAX(trial_number) AS max_trial FROM learning_log_entries "
            "WHERE intervention_description = ?",
            (intervention_description,),
        ).fetchone()
        current_max = row["max_trial"]
        return (current_max or 0) + 1
