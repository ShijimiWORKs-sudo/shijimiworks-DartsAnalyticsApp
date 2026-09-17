"""Minimal, dependency-free SQLite migration runner.

Migrations are plain .sql files under db/schema/, named NNNN_description.sql.
Applied migrations are tracked in a schema_migrations table so re-running
is a no-op (idempotent) and partial upgrades are possible later.

Each migration is applied atomically: if any statement in it fails, every
DDL change it made is rolled back and the version is NOT recorded as
applied, so a retry starts from a clean slate. This matters because
sqlite3.Connection.executescript() issues an implicit COMMIT before
running and does not itself provide atomicity across the statements in the
script — using it directly would let a migration partially apply (e.g.
table 5 of 18 created) without being recorded, so a retry would then fail
with "table already exists" and the database would be stuck. Statements
are executed one at a time inside an explicit transaction instead.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_DIR = Path(__file__).parent / "schema"


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     TEXT PRIMARY KEY,
            applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()


def _applied_versions(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {row["version"] for row in rows}


def available_migrations() -> list[Path]:
    return sorted(SCHEMA_DIR.glob("*.sql"))


def _split_sql_statements(sql: str) -> list[str]:
    """Split a .sql file's contents into individual statements.

    Strips full-line `--` comments and splits on ';'. This is a simple
    splitter, not a general SQL parser — it assumes (true for every
    migration in this repo) that no statement contains a semicolon inside
    a string literal, trigger body, or similar. If a future migration
    needs that, this function must be revisited rather than silently
    producing a wrong split.
    """
    lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
    statements = "\n".join(lines).split(";")
    return [stmt.strip() for stmt in statements if stmt.strip()]


def _apply_migration_sql(conn: sqlite3.Connection, version: str, sql: str) -> None:
    """Apply one migration's SQL and record it as applied, atomically.

    On any failure, rolls back every change this migration made (including
    the schema_migrations insert) and re-raises — the caller sees the
    original exception, the schema is left exactly as it was beforehand.
    """
    try:
        conn.execute("BEGIN")
        for statement in _split_sql_statements(sql):
            conn.execute(statement)
        conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def apply_migrations(conn: sqlite3.Connection) -> list[str]:
    """Apply any not-yet-applied migrations, in filename order.

    Returns the list of migration versions newly applied (empty if the
    schema was already up to date — this makes the call idempotent, which
    Phase 0's migration test relies on). Stops at the first migration that
    fails (and leaves it un-applied per _apply_migration_sql); later
    migrations are not attempted that run.
    """
    _ensure_migrations_table(conn)
    applied = _applied_versions(conn)
    newly_applied: list[str] = []

    for migration_path in available_migrations():
        version = migration_path.stem
        if version in applied:
            continue
        sql = migration_path.read_text(encoding="utf-8")
        _apply_migration_sql(conn, version, sql)
        newly_applied.append(version)

    return newly_applied


def schema_version(conn: sqlite3.Connection) -> str | None:
    _ensure_migrations_table(conn)
    row = conn.execute(
        "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
    ).fetchone()
    return row["version"] if row else None
