"""GridCloner — deterministic 2D grid layout for N parallel envs.

Mirrors `omni.isaac.cloner.GridCloner` (Isaac Sim 4.x) public surface:

    cloner = GridCloner(spacing=4.0)
    cloner.define_base_env("/World/envs/env_0")
    paths = cloner.generate_paths("/World/envs/env", count=1024)
    # cloner.clone(...) is a no-op stub at R1.x — scene-graph integration
    # arrives with kami-render WGSL render delegate (R1.4+); the grid math
    # and prim-path generation are the only pieces RL workflows actually
    # need from this class.
    pos = cloner.position_for_env(env_idx=42)  # → (x, y, z) world position

stdlib-only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Cloner:
    """Base cloner — overridden by GridCloner / RotatingCloner / etc."""
    base_env_path: Optional[str] = None
    _generated_paths: list = field(default_factory=list)

    def define_base_env(self, prim_path: str) -> None:
        self.base_env_path = prim_path

    def generate_paths(self, prefix: str, count: int) -> list:
        """Generate count prim paths formatted `{prefix}_{i}`."""
        self._generated_paths = [f"{prefix}_{i}" for i in range(count)]
        return list(self._generated_paths)

    def clone(self, source_prim_path: str, prim_paths: list,
              replicate_physics: bool = True) -> None:
        """No-op at R1.x — kami substrate has no scene graph yet.

        The grid_cloner.GridCloner integration with kami-render happens at
        R1.4 (WGSL render delegate). For now, this method just stashes
        bookkeeping so existing Isaac Sim scripts that call clone() don't
        crash.
        """
        self._cloned_source = source_prim_path
        self._cloned_targets = list(prim_paths)
        self._replicate_physics = replicate_physics


@dataclass
class GridCloner(Cloner):
    """Lays out N env instances in a square-ish grid in the xy plane.

    `spacing` is centre-to-centre distance between adjacent envs. By default
    the grid is square (ceil(sqrt(N)) per side); pass `num_per_row` to
    override. The grid is centred at the world origin so positive x is right,
    positive y is forward (RH coordinate system).
    """
    spacing: float = 4.0
    num_per_row: Optional[int] = None
    z_offset: float = 0.0

    def _grid_dim(self, count: int) -> int:
        if self.num_per_row is not None and self.num_per_row > 0:
            return int(self.num_per_row)
        return max(1, int(math.ceil(math.sqrt(count))))

    def position_for_env(self, env_idx: int, count: Optional[int] = None) -> tuple:
        """Return the world-frame (x, y, z) position for env `env_idx`.

        `count` is used only to determine the grid edge length when
        num_per_row is None; if omitted, uses env_idx + 1 (i.e. assumes
        you're past the largest seen index). The grid is centred at the
        origin so that for an N×N grid the centre row/col straddles 0.
        """
        n = count if count is not None else env_idx + 1
        per_row = self._grid_dim(n)
        row = env_idx // per_row
        col = env_idx % per_row
        num_rows = max(1, int(math.ceil(n / per_row)))
        # Centre offset: shift so that envs span [-extent/2, +extent/2].
        x_centre = (per_row - 1) * 0.5
        y_centre = (num_rows - 1) * 0.5
        x = (col - x_centre) * self.spacing
        y = (row - y_centre) * self.spacing
        return (float(x), float(y), float(self.z_offset))

    def positions_for_envs(self, count: int) -> list:
        """All N positions in env_idx order. O(N)."""
        return [self.position_for_env(i, count) for i in range(count)]

    def grid_dim(self, count: int) -> tuple:
        """Returns (cols, rows) of the layout grid."""
        per_row = self._grid_dim(count)
        num_rows = max(1, int(math.ceil(count / per_row)))
        return (per_row, num_rows)
