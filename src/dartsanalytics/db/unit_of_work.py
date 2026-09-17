"""Unit of Work: composes the SQLite repositories behind one connection so
a caller gets atomic, multi-repository writes (docs §10 resolution).

Usage (the ``UI -> Application Service`` half of the pattern talks only to
this and to the Repository Interfaces, never to sqlite3 directly)::

    with SqliteUnitOfWork(db_path) as uow:
        uow.accounts.save(account)
        uow.players.save(player)
        uow.sessions.save_session(session)
        # commits automatically on clean exit

    with SqliteUnitOfWork(db_path) as uow:
        uow.sessions.save_session(broken_session)
        raise RuntimeError("something else failed")
    # -> rolled back; broken_session was never persisted

``apply_migrations`` runs on every connect (it's idempotent — see
db/migrate.py), so a UnitOfWork never has to be preceded by a separate
"init db" step; opening one against a fresh path bootstraps the schema.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType

from dartsanalytics.db.connection import DEFAULT_DB_PATH, connect
from dartsanalytics.db.migrate import apply_migrations
from dartsanalytics.db.repositories.sqlite_repositories import (
    SqliteAccountRepository,
    SqliteAnalysisReportRepository,
    SqliteCalibrationRepository,
    SqliteEquipmentRepository,
    SqliteExperimentRepository,
    SqliteGripAnalysisRepository,
    SqliteLearningLogRepository,
    SqliteMediaRepository,
    SqlitePlayerRepository,
    SqlitePoseFeatureRepository,
    SqliteSessionRepository,
)


class SqliteUnitOfWork:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        self.conn: sqlite3.Connection | None = None

    def __enter__(self) -> "SqliteUnitOfWork":
        self.conn = connect(self._db_path)
        apply_migrations(self.conn)
        self.accounts = SqliteAccountRepository(self.conn)
        self.players = SqlitePlayerRepository(self.conn)
        self.equipment = SqliteEquipmentRepository(self.conn)
        self.sessions = SqliteSessionRepository(self.conn)
        self.calibrations = SqliteCalibrationRepository(self.conn)
        self.media = SqliteMediaRepository(self.conn)
        self.pose_features = SqlitePoseFeatureRepository(self.conn)
        self.grip_runs = SqliteGripAnalysisRepository(self.conn)
        self.analysis_reports = SqliteAnalysisReportRepository(self.conn)
        self.experiments = SqliteExperimentRepository(self.conn)
        self.learning_log = SqliteLearningLogRepository(self.conn)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self.conn is not None
        try:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
        finally:
            self.conn.close()
            self.conn = None

    def commit(self) -> None:
        assert self.conn is not None
        self.conn.commit()

    def rollback(self) -> None:
        assert self.conn is not None
        self.conn.rollback()
