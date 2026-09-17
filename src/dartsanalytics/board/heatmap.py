"""Grouping heatmap as a density grid (docs §10 ヒートマップ).

Phase 3 produces the underlying data, not a rendered image — turning this
into a PNG/overlay is UI work better done once Phase 4's video/UI layer
exists (rendering choices — colormap, board image overlay, resolution —
belong with the rest of the UI, not the analysis core). build_heatmap()
returns a plain 2D count grid over the normalized [-1, 1] x [-1, 1] board
area, which is enough to satisfy §27's "グルーピング指標が再計算可能"
completion condition and is trivial to feed into any renderer later.
"""

from __future__ import annotations

import numpy as np


def build_heatmap(
    points: list[tuple[float, float]], *, grid_size: int = 20, extent: float = 1.5
) -> np.ndarray:
    """Bin normalized (x, y) points into a grid_size x grid_size count grid
    covering [-extent, extent] on each axis (extent > 1.0 so throws just
    outside the board's outer ring aren't silently dropped)."""
    if grid_size < 1:
        raise ValueError(f"grid_size must be >= 1, got {grid_size}")
    if not points:
        return np.zeros((grid_size, grid_size), dtype=np.int64)

    arr = np.array(points, dtype=np.float64)
    counts, _, _ = np.histogram2d(
        arr[:, 0],
        arr[:, 1],
        bins=grid_size,
        range=[[-extent, extent], [-extent, extent]],
    )
    return counts.astype(np.int64)
