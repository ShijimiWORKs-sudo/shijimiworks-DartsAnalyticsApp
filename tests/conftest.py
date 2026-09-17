import sys
from pathlib import Path

# Allow `import dartsanalytics` without an editable install (keeps the
# zero-dependency bar low for Phase 0 — no pip install required just to
# run the test suite in CI-less environments).
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from dartsanalytics.db import apply_migrations, connect


@pytest.fixture
def db_conn():
    """Fresh in-memory DB with migrations applied, per test."""
    conn = connect(":memory:")
    apply_migrations(conn)
    yield conn
    conn.close()
