"""'よく刺さるナンバー' analysis (docs §12).

docs §12 lists 7 items to separate:

1. 実際に入ったセグメント頻度 — computed here (segment_counts).
2. SINGLE/DOUBLE/TRIPLE別頻度 — computed here (ring_counts).
3. 左右位置偏り — already GroupingStats.horizontal_bias
   (dartsanalytics.board.grouping); not duplicated here.
4. 上下位置偏り — already GroupingStats.vertical_bias; not duplicated here.
5. BULLからの距離 — already GroupingStats.mean/rms/percentile distances;
   not duplicated here.
6. 連続して同方向へ外れる頻度 — computed here (horizontal_streaks /
   vertical_streaks).
7. ラウンド後半での偏り — dartsanalytics.integrated.late_round (a separate
   module; comparing two GroupingStats sub-populations is a distinct
   concern from per-throw frequency counting).

docs §12 also asks for "隣接セグメントを含めた方向性を可視化する" (visualize
directionality including adjacent segments) — that is a UI-rendering
concern. This codebase has no UI layer in any Phase yet (see AGENTS.md's
Phase table), so only the underlying frequency *data* is produced here;
rendering/visualization is left for whichever future UI work consumes it.
"""

from __future__ import annotations

from dataclasses import dataclass

from dartsanalytics.common.enums import Ring
from dartsanalytics.models.entities import Throw


def _sign(v: float) -> int:
    if v > 0:
        return 1
    if v < 0:
        return -1
    return 0


@dataclass(frozen=True)
class DirectionStreaks:
    axis: str  # "horizontal" or "vertical"
    max_streak: int  # longest run of consecutive same-direction throws (>=1; 1 = no repeat ever)
    streak_lengths: list[int]  # every run of length >= 2, in chronological order

    def to_dict(self) -> dict:
        return {"axis": self.axis, "max_streak": self.max_streak, "streak_lengths": self.streak_lengths}


def find_direction_streaks(values_in_order: list[float], *, axis: str) -> DirectionStreaks:
    """`values_in_order`: normalized_x (axis="horizontal") or normalized_y
    (axis="vertical") values in throw order. A value of exactly 0.0 (dead
    center on that axis) breaks any streak rather than joining either
    direction — it isn't "left" or "right"."""
    if axis not in ("horizontal", "vertical"):
        raise ValueError(f"axis must be 'horizontal' or 'vertical', got {axis!r}")
    if not values_in_order:
        return DirectionStreaks(axis=axis, max_streak=0, streak_lengths=[])

    runs: list[int] = []
    current_sign = _sign(values_in_order[0])
    current_len = 1
    for v in values_in_order[1:]:
        s = _sign(v)
        if s != 0 and s == current_sign:
            current_len += 1
        else:
            runs.append(current_len)
            current_sign = s
            current_len = 1
    runs.append(current_len)

    return DirectionStreaks(axis=axis, max_streak=max(runs), streak_lengths=[r for r in runs if r >= 2])


@dataclass(frozen=True)
class FrequentSegmentStats:
    n: int
    segment_counts: dict[str, int]
    ring_counts: dict[str, int]
    horizontal_streaks: DirectionStreaks
    vertical_streaks: DirectionStreaks

    def to_dict(self) -> dict:
        return {
            "n": self.n,
            "segment_counts": self.segment_counts,
            "ring_counts": self.ring_counts,
            "horizontal_streaks": self.horizontal_streaks.to_dict(),
            "vertical_streaks": self.vertical_streaks.to_dict(),
        }


def compute_frequent_segment_stats(throws: list[Throw]) -> FrequentSegmentStats:
    if not throws:
        raise ValueError("compute_frequent_segment_stats requires at least one throw")

    ordered = sorted(throws, key=lambda t: t.throw_number_in_session)

    segment_counts: dict[str, int] = {}
    ring_counts: dict[str, int] = {r.value: 0 for r in Ring}
    for t in ordered:
        # actual_target (§5.2の実着弾) is preferred over the plain `segment`
        # field when both are present — they're normally the same value,
        # but actual_target is the field the spec designates as ground truth.
        seg = t.actual_target or t.segment
        if seg:
            segment_counts[seg] = segment_counts.get(seg, 0) + 1
        if t.ring is not None:
            ring_counts[t.ring.value] += 1

    xs = [t.normalized_x for t in ordered if t.normalized_x is not None]
    ys = [t.normalized_y for t in ordered if t.normalized_y is not None]

    return FrequentSegmentStats(
        n=len(ordered),
        segment_counts=segment_counts,
        ring_counts=ring_counts,
        horizontal_streaks=find_direction_streaks(xs, axis="horizontal"),
        vertical_streaks=find_direction_streaks(ys, axis="vertical"),
    )
