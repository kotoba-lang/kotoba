"""Procedural terrain generators — height-field outputs for legged locomotion.

Each generator returns a HeightField (square grid of z-elevations). The
generators are seed-deterministic (LCG matching kami_shugyo::Lcg constants)
so produced terrains are byte-identical to a Rust port in a future iter.

All terrains are returned in METRES with the origin at the centre of the
heightfield. `cell_size` is the world-frame edge length of each cell, so the
total terrain side length is `cell_size * (rows - 1)` (vertex grid).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# LCG matching kami_shugyo / nv_compat conventions → cross-language reproducible.
class _Lcg:
    def __init__(self, seed: int):
        self.state = (seed * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF

    def next_u01(self) -> float:
        self.state = (self.state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return ((self.state >> 33) & 0x7FFFFFFF) / float(1 << 31)

    def next_uniform(self, low: float, high: float) -> float:
        return low + (high - low) * self.next_u01()


@dataclass
class HeightField:
    """Grid of elevations centred at (0, 0).

    `heights[row][col]` is the z-elevation (m) at the vertex at world position
    `(col*cell_size - extent_x/2, row*cell_size - extent_y/2)`.
    """
    rows: int
    cols: int
    cell_size: float
    heights: list  # list[list[float]], rows x cols
    name: str = "terrain"

    def extent_x(self) -> float:
        """Total side length in x direction (m)."""
        return self.cell_size * max(0, self.cols - 1)

    def extent_y(self) -> float:
        """Total side length in y direction (m)."""
        return self.cell_size * max(0, self.rows - 1)

    def min_height(self) -> float:
        return min(min(row) for row in self.heights)

    def max_height(self) -> float:
        return max(max(row) for row in self.heights)

    def height_at(self, row: int, col: int) -> float:
        return self.heights[row][col]


def _empty_grid(rows: int, cols: int, fill: float = 0.0) -> list:
    return [[fill] * cols for _ in range(rows)]


def flat_terrain(rows: int = 64, cols: int = 64, cell_size: float = 0.1,
                 elevation: float = 0.0) -> HeightField:
    """All cells at the same elevation. Baseline for sanity tests."""
    return HeightField(rows=rows, cols=cols, cell_size=cell_size,
                       heights=_empty_grid(rows, cols, elevation),
                       name="flat")


def random_uniform_terrain(rows: int = 64, cols: int = 64, cell_size: float = 0.1,
                           noise_range: tuple = (-0.05, 0.05),
                           seed: int = 0) -> HeightField:
    """Each cell sampled independently from U(low, high).

    Use for locomotion-robustness training (forces the policy to handle
    micro-scale ground variation). For long-wavelength terrain use one of
    the structured generators (pyramid_*, stepping_stones).
    """
    rng = _Lcg(seed)
    low, high = noise_range
    heights = [
        [rng.next_uniform(low, high) for _ in range(cols)]
        for _ in range(rows)
    ]
    return HeightField(rows=rows, cols=cols, cell_size=cell_size,
                       heights=heights, name="random_uniform")


def pyramid_stairs_terrain(rows: int = 64, cols: int = 64, cell_size: float = 0.1,
                           step_height: float = 0.05, step_width: int = 4,
                           pyramid_height: float = 0.5) -> HeightField:
    """Concentric stair rings rising toward the centre.

    Used for stair-climbing curricula. Step ring k (0 = outermost) is at
    elevation `step_height * k`, clamped to `pyramid_height` at the top.
    `step_width` is in cells per ring.
    """
    heights = _empty_grid(rows, cols, 0.0)
    cy = (rows - 1) * 0.5
    cx = (cols - 1) * 0.5
    max_radius_cells = min(cy, cx)
    for r in range(rows):
        for c in range(cols):
            dist_cells = max(abs(r - cy), abs(c - cx))  # Chebyshev (square rings)
            # Distance from outer edge → which ring we're in (ring 0 = outermost)
            edge_dist = max_radius_cells - dist_cells
            ring = int(edge_dist // step_width)
            z = ring * step_height
            if z > pyramid_height:
                z = pyramid_height
            heights[r][c] = z
    return HeightField(rows=rows, cols=cols, cell_size=cell_size,
                       heights=heights, name="pyramid_stairs")


def pyramid_sloped_terrain(rows: int = 64, cols: int = 64, cell_size: float = 0.1,
                           slope: float = 0.2, max_height: float = 0.5) -> HeightField:
    """Radially-sloped pyramid (continuous version of pyramid_stairs).

    Elevation increases linearly with Chebyshev distance to the centre at
    rate `slope` m per cell, capped at `max_height`.
    """
    heights = _empty_grid(rows, cols, 0.0)
    cy = (rows - 1) * 0.5
    cx = (cols - 1) * 0.5
    max_radius_cells = min(cy, cx)
    for r in range(rows):
        for c in range(cols):
            dist_cells = max(abs(r - cy), abs(c - cx))
            edge_dist = max_radius_cells - dist_cells
            z = edge_dist * slope * cell_size
            if z > max_height:
                z = max_height
            if z < 0:
                z = 0.0
            heights[r][c] = z
    return HeightField(rows=rows, cols=cols, cell_size=cell_size,
                       heights=heights, name="pyramid_sloped")


def stepping_stones_terrain(rows: int = 64, cols: int = 64, cell_size: float = 0.1,
                            stone_radius: int = 3, stone_height: float = 0.15,
                            stone_count: int = 30, seed: int = 0) -> HeightField:
    """Sparse raised circles (stones) on flat ground.

    Used for foothold precision tasks. `stone_radius` is in cells; each
    stone is a flat disc raised to `stone_height`. `stone_count` discs are
    placed at random non-overlapping cell centres.
    """
    heights = _empty_grid(rows, cols, 0.0)
    rng = _Lcg(seed)
    placed: list = []
    attempts = 0
    while len(placed) < stone_count and attempts < stone_count * 10:
        attempts += 1
        r = int(rng.next_uniform(stone_radius, rows - stone_radius - 1))
        c = int(rng.next_uniform(stone_radius, cols - stone_radius - 1))
        # Reject if overlaps any prior stone (centre-to-centre Chebyshev distance).
        if any(max(abs(r - pr), abs(c - pc)) < 2 * stone_radius for pr, pc in placed):
            continue
        placed.append((r, c))
        # Paint disc (Chebyshev for simplicity = square stones).
        for dr in range(-stone_radius, stone_radius + 1):
            for dc in range(-stone_radius, stone_radius + 1):
                if dr * dr + dc * dc <= stone_radius * stone_radius:
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < rows and 0 <= cc < cols:
                        heights[rr][cc] = stone_height
    return HeightField(rows=rows, cols=cols, cell_size=cell_size,
                       heights=heights, name="stepping_stones")


def discrete_obstacles_terrain(rows: int = 64, cols: int = 64, cell_size: float = 0.1,
                               obstacle_size: int = 4, obstacle_height: float = 0.1,
                               obstacle_count: int = 20, seed: int = 0) -> HeightField:
    """Random axis-aligned box obstacles on flat ground.

    Used for obstacle-avoidance training. Each obstacle is a flat-topped
    square of side `obstacle_size` cells raised to `obstacle_height`.
    """
    heights = _empty_grid(rows, cols, 0.0)
    rng = _Lcg(seed)
    for _ in range(obstacle_count):
        r = int(rng.next_uniform(0, rows - obstacle_size - 1))
        c = int(rng.next_uniform(0, cols - obstacle_size - 1))
        for dr in range(obstacle_size):
            for dc in range(obstacle_size):
                rr, cc = r + dr, c + dc
                if 0 <= rr < rows and 0 <= cc < cols:
                    heights[rr][cc] = obstacle_height
    return HeightField(rows=rows, cols=cols, cell_size=cell_size,
                       heights=heights, name="discrete_obstacles")
