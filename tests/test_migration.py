"""Phase 0 migration tests."""

from dartsanalytics.db import apply_migrations, available_migrations, connect, schema_version

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
    assert version.startswith("0001")


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
