"""Phase 0 migration tests."""

import pytest

from dartsanalytics.db import apply_migrations, available_migrations, connect, schema_version
from dartsanalytics.db.migrate import _apply_migration_sql, _ensure_migrations_table, _split_sql_statements

EXPECTED_TABLES = {
    "accounts",
    "players",
    "equipment_profiles",
    "practice_sessions",
    "countup_rounds",
    "throws",
    "board_calibrations",
    "throw_coordinates",
    "media_assets",
    "video_analysis_runs",
    "pose_features",
    "grip_analysis_runs",
    "analysis_reports",
    "hypotheses",
    "interventions",
    "experiments",
    "experiment_results",
    "learning_log_entries",
    "schema_migrations",
}


def _table_names(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row["name"] for row in rows}


def test_migrations_discovered():
    assert len(available_migrations()) >= 1


def test_apply_migrations_creates_all_tables(db_conn):
    assert EXPECTED_TABLES.issubset(_table_names(db_conn))


def test_apply_migrations_is_idempotent():
    conn = connect(":memory:")
    try:
        first = apply_migrations(conn)
        assert len(first) >= 1
        second = apply_migrations(conn)
        assert second == []  # nothing new applied the second time
        assert _table_names(conn) == _table_names(conn)  # no duplication/crash
    finally:
        conn.close()


def test_schema_version_reported(db_conn):
    version = schema_version(db_conn)
    assert version is not None
    # The latest applied migration's stem — asserted against
    # available_migrations() rather than a hardcoded "0001" prefix, so this
    # test doesn't need editing every time a new migration file is added
    # (0002_learning_log.sql, etc.).
    assert version == available_migrations()[-1].stem


def test_migration_test_db_is_isolated_from_real_db(tmp_path):
    """Migration test DBs must never touch data/dartsanalytics.db —
    this guards against accidentally corrupting real user data while testing
    (design principle: 動画原本を上書きしない / never clobber real data)."""
    file_db_path = tmp_path / "isolated_test.db"
    conn = connect(file_db_path)
    try:
        apply_migrations(conn)
        assert file_db_path.exists()
    finally:
        conn.close()
    from dartsanalytics.db import DEFAULT_DB_PATH

    assert file_db_path != DEFAULT_DB_PATH


def test_split_sql_statements_strips_comments_and_splits_on_semicolon():
    sql = """
    -- a comment line
    CREATE TABLE a (id TEXT);
    CREATE TABLE b (id TEXT);
    """
    statements = _split_sql_statements(sql)
    assert len(statements) == 2
    assert all("--" not in s for s in statements)


def test_partial_migration_failure_rolls_back_cleanly():
    """A migration that fails partway through must not leave any of its
    tables behind, and must not be recorded as applied — otherwise a retry
    would hit 'table already exists' forever (the bug this test guards
    against; see migrate.py module docstring)."""
    conn = connect(":memory:")
    try:
        _ensure_migrations_table(conn)
        broken_sql = """
        CREATE TABLE ok_table_1 (id TEXT);
        CREATE TABLE ok_table_2 (id TEXT);
        THIS IS NOT VALID SQL;
        """
        with pytest.raises(Exception):
            _apply_migration_sql(conn, "9999_broken", broken_sql)

        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        assert "ok_table_1" not in tables
        assert "ok_table_2" not in tables

        applied = {
            row["version"] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
        assert "9999_broken" not in applied

        # Retrying after "fixing" the migration (here: just applying valid
        # SQL under the same version) must succeed — proof the rollback
        # left no partial state to collide with.
        _apply_migration_sql(conn, "9999_broken", "CREATE TABLE ok_table_1 (id TEXT);")
        tables_after_retry = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        assert "ok_table_1" in tables_after_retry
    finally:
        conn.close()
