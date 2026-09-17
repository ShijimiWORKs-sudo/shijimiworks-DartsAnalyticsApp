"""Standard steel/soft-tip dartboard scoring.

Kept separate from the mock generator so Phase 2's real DARTSLIVE HOME
adapter (once it exists) can reuse the exact same scoring rules instead
of duplicating them.
"""

from __future__ import annotations

from dartsanalytics.common.enums import Ring

# Standard board numbering, clockwise from 20 — not used for geometry yet
# (that's Phase 3's job), only to pick plausible segment numbers for the
# mock generator.
BOARD_NUMBERS = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]


def score_for(ring: Ring, number: int | None) -> int:
    """Compute the point value for a ring/number combination.

    `number` is the 1-20 segment; ignored (must be None) for BULL/DBULL/MISS.
    """
    if ring == Ring.MISS:
        return 0
    if ring == Ring.BULL:
        return 25
    if ring == Ring.DBULL:
        return 50
    if number is None or not 1 <= number <= 20:
        raise ValueError(f"number must be 1..20 for ring={ring}, got {number!r}")
    if ring == Ring.SINGLE:
        return number
    if ring == Ring.DOUBLE:
        return number * 2
    if ring == Ring.TRIPLE:
        return number * 3
    raise ValueError(f"unhandled ring: {ring!r}")


def format_segment(ring: Ring, number: int | None) -> str:
    """Human/DB-friendly segment label, e.g. 'T20', 'D16', 'S5', 'BULL', 'DBULL', 'MISS'."""
    if ring in (Ring.BULL, Ring.DBULL, Ring.MISS):
        return ring.value
    prefix = {Ring.SINGLE: "S", Ring.DOUBLE: "D", Ring.TRIPLE: "T"}[ring]
    return f"{prefix}{number}"
