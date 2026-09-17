"""Minimal, dependency-free SQLite migration runner.

Migrations are plain .sql files under db/schema/, named NNNN_description.sql.
Applied migrations are tracked in a schema_migrations table so re-running
is a no-op (idempotent) and partial upgrades are possible later.
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


def _applied_versions(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {row["version"] for row in rows}


def available_migrations() -> list[Path]:
    return sorted(SCHEMA_DIR.glob("*.sql"))


def apply_migrations(conn: sqlite3.Connection) -> list[str]:
    """Apply any not-yet-applied migrations, in filename order.

    Returns the list of migration versions newly applied (empty if the
    schema was already up to date — this makes the call idempotent, which
    Phase 0's migration test relies on).
    """
    _ensure_migrations_table(conn)
    applied = _applied_versions(conn)
    newly_applied: list[str] = []

    for migration_path in available_migrations():
        version = migration_path.stem
        if version in applied:
            continue
        sql = migration_path.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_migrations (version) VALUES (?)", (version,)
        )
        newly_applied.append(version)

    conn.commit()
    return newly_applied


def schema_version(conn: sqlite3.Connection) -> str | None:
    _ensure_migrations_table(conn)
    row = conn.execute(
        "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
    ).fetchone()
    return row["version"] if row else None
