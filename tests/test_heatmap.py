import numpy as np

from dartsanalytics.board.heatmap import build_heatmap
from tests.fixtures.board_patterns import all_center, left_right_even_split


def test_build_heatmap_shape():
    grid = build_heatmap(all_center(), grid_size=10)
    assert grid.shape == (10, 10)


def test_build_heatmap_total_count_matches_input_size():
    points = all_center()
    grid = build_heatmap(points, grid_size=10)
    assert int(grid.sum()) == len(points)


def test_build_heatmap_all_center_concentrates_in_middle_bins():
    grid = build_heatmap(all_center(), grid_size=10, extent=1.5)
    mid = 10 // 2
    # All points at (0,0) should land in one of the central bins.
    center_region = grid[mid - 1 : mid + 1, mid - 1 : mid + 1]
    assert center_region.sum() == 24


def test_build_heatmap_splits_across_two_regions_for_left_right_fixture():
    grid = build_heatmap(left_right_even_split(), grid_size=10, extent=1.5)
    mid = 10 // 2
    left_half = grid[:mid, :].sum()
    right_half = grid[mid:, :].sum()
    assert left_half == 12
    assert right_half == 12


def test_build_heatmap_empty_input_returns_zero_grid():
    grid = build_heatmap([], grid_size=5)
    assert grid.shape == (5, 5)
    assert grid.sum() == 0
