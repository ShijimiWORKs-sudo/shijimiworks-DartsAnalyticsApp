"""Recovery tests (docs §12's "Recovery" category): DB failure modes.

The other three docs §12 Recovery items (interrupted analysis, invalid
video, BLE disconnect) are already covered elsewhere:
  - invalid video: tests/test_ffmpeg_tools.py
    (test_probe_metadata_missing_file_raises_probe_error,
    test_probe_metadata_missing_binary_raises_clear_error)
  - BLE disconnect / not-yet-connected: tests/test_dartslive_adapter.py
    (test_mock_adapter_requires_connect_before_events,
    test_unimplemented_ble_adapter_refuses_to_guess)
  - interrupted analysis: tests/test_migration.py
    (test_partial_migration_failure_rolls_back_cleanly) and
    tests/test_repositories.py
    (test_unit_of_work_rolls_back_whole_transaction_on_error) already
    cover "a multi-step DB write gets interrupted partway"

This file adds the DB-specific failure modes that weren't covered yet:
opening a corrupted/non-database file, and a read-only destination.
"""

from __future__ import annotations

import sqlite3

import pytest

from dartsanalytics.db.unit_of_work import SqliteUnitOfWork
from dartsanalytics.models.entities import Account


def test_corrupted_db_file_raises_clear_error_not_silent_corruption(tmp_path):
    """A .db path that exists but isn't a valid SQLite file (e.g. a
    partially-written or corrupted file from a crash mid-write) must
    surface a clear sqlite3 error on open, not silently proceed as if it
    were empty (which would risk overwriting/losing whatever data was
    there)."""
    db_path = tmp_path / "corrupted.db"
    db_path.write_bytes(b"this is not a sqlite database file, just garbage bytes")

    with pytest.raises(sqlite3.DatabaseError):
        with SqliteUnitOfWork(db_path) as uow:
            uow.accounts.save(Account(display_name="洋典"))


def test_db_path_that_is_actually_a_directory_raises_clear_error(tmp_path):
    """A destination path that collides with an existing directory (e.g.
    a misconfigured settings value, or a sync tool that created a folder
    where the DB file should be) must fail loudly on open, not silently
    write somewhere unexpected. Chosen over a read-only-permissions test
    because permission bits don't block root (this sandbox runs as root),
    so a permission-based failure mode wouldn't reproduce reliably here —
    a path-is-a-directory collision fails regardless of privilege."""
    db_path_that_is_a_directory = tmp_path / "app.db"
    db_path_that_is_a_directory.mkdir()

    with pytest.raises((sqlite3.OperationalError, IsADirectoryError, OSError)):
        with SqliteUnitOfWork(db_path_that_is_a_directory) as uow:
            uow.accounts.save(Account(display_name="洋典"))


def test_existing_valid_db_survives_a_failed_open_attempt_elsewhere(tmp_path):
    """A corrupted-file open failure on ONE path must not affect a
    separate, valid DB file — failures should be scoped to the connection
    that hit them, never leak into unrelated app state."""
    good_db = tmp_path / "good.db"
    with SqliteUnitOfWork(good_db) as uow:
        account = Account(display_name="洋典")
        uow.accounts.save(account)

    bad_db = tmp_path / "bad.db"
    bad_db.write_bytes(b"not a database")
    with pytest.raises(sqlite3.DatabaseError):
        with SqliteUnitOfWork(bad_db) as uow:
            uow.accounts.save(Account(display_name="別のアカウント"))

    # The good DB is completely unaffected by the other connection's failure.
    with SqliteUnitOfWork(good_db) as uow:
        assert uow.accounts.get(account.account_id) is not None
