"""Release/follow-through CANDIDATE detection (docs §13:
"release/follow-through候補" — explicitly a candidate, not a confirmed
moment).

Heuristic: the release moment is approximated as the frame(s) with peak
wrist speed, since the dart leaves the hand at roughly the fastest point
of the throwing motion. This is a reasonable first-pass heuristic, NOT a
validated biomechanical model — confidence is deliberately capped well
below 1.0 (0.7 max) so nothing downstream treats a candidate as a
measurement. See docs/codex/reports/phase5_notes.md.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from dartsanalytics.common.enums import DataKind

MAX_HEURISTIC_CONFIDENCE = 0.7
MIN_HEURISTIC_CONFIDENCE = 0.1

WristSample = tuple[float, float, float]  # (timestamp_sec, x, y)


@dataclass(frozen=True)
class ReleaseCandidate:
    frame_index: int  # index into the input track's velocity list (i.e. the *later* of the two samples spanning this velocity)
    timestamp_sec: float
    velocity: float  # normalized-coordinate units per second
    confidence: float
    data_kind: DataKind = DataKind.ESTIMATED

    def to_dict(self) -> dict:
        return {
            "frame_index": self.frame_index,
            "timestamp_sec": self.timestamp_sec,
            "velocity": self.velocity,
            "confidence": self.confidence,
            "data_kind": self.data_kind.value,
        }


def find_release_candidates(wrist_track: list[WristSample], *, top_n: int = 1) -> list[ReleaseCandidate]:
    """`wrist_track`: (timestamp_sec, x, y) samples in increasing time order.

    Returns up to `top_n` candidates, highest velocity first. Empty if
    there are fewer than 2 samples or no positive time deltas (can't
    compute a velocity at all — never guesses).
    """
    if len(wrist_track) < 2:
        return []
    if top_n < 1:
        raise ValueError(f"top_n must be >= 1, got {top_n}")

    velocities: list[tuple[int, float, float]] = []  # (index, timestamp, velocity)
    for i in range(1, len(wrist_track)):
        t0, x0, y0 = wrist_track[i - 1]
        t1, x1, y1 = wrist_track[i]
        dt = t1 - t0
        if dt <= 0:
            continue
        v = math.hypot(x1 - x0, y1 - y0) / dt
        velocities.append((i, t1, v))

    if not velocities:
        return []

    median_v = statistics.median(v for _, _, v in velocities)
    ranked = sorted(velocities, key=lambda item: item[2], reverse=True)[:top_n]

    candidates = []
    for idx, t, v in ranked:
        ratio = (v / median_v) if median_v > 0 else 1.0
        # Monotonic in how much this peak exceeds the median, capped —
        # never a claim of certainty, always framed as "candidate".
        confidence = min(MAX_HEURISTIC_CONFIDENCE, MIN_HEURISTIC_CONFIDENCE + 0.1 * math.log1p(ratio))
        confidence = max(MIN_HEURISTIC_CONFIDENCE, confidence)
        candidates.append(ReleaseCandidate(frame_index=idx, timestamp_sec=t, velocity=v, confidence=confidence))
    return candidates
