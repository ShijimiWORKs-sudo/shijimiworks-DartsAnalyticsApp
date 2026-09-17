#!/usr/bin/env python3
"""Phase 0 startup check: run migrations against the real (file-based) DB
and report the resulting schema. This is the "起動確認" referenced in
AGENTS.md / docs/codex/CODEX_...md §8 completion report.

Usage: python scripts/bootstrap_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dartsanalytics.db import DEFAULT_DB_PATH, apply_migrations, connect, schema_version  # noqa: E402


def main() -> int:
    conn = connect(DEFAULT_DB_PATH)
    try:
        newly_applied = apply_migrations(conn)
        version = schema_version(conn)
        tables = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        print(f"DB path: {DEFAULT_DB_PATH.resolve()}")
        print(f"Newly applied migrations: {newly_applied or '(none — already up to date)'}")
        print(f"Schema version: {version}")
        print(f"Tables ({len(tables)}): {sorted(tables)}")
        print("OK: bootstrap check passed")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
