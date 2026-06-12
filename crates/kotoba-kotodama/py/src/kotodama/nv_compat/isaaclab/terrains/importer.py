"""TerrainImporter — declarative terrain loader.

Mirror of `isaaclab.terrains.TerrainImporter` (Isaac Lab 1.x). The canonical
Isaac Lab API for getting terrain onto the stage. Four terrain types:

  - "plane"       — infinite flat ground (default for cartpole-class scenes)
  - "heightfield" — caller supplies a `HeightField` from
                    `isaaclab.terrains.terrain_generator`
  - "generator"   — `TerrainGeneratorCfg` describes a grid of sub-terrains
                    sampled from `sub_terrains` cfgs; the importer assembles
                    the full terrain mesh + per-env origin grid
  - "usd"         — load terrain mesh from a USD/OBJ/STL file (UsdFileCfg)

TerrainImporter owns:
  - env_origins[env_idx]    — world-frame (x, y, z) per env
  - terrain_levels[env_idx] — curriculum level per env (int; 0 = easiest)
  - terrain_types[env_idx]  — which sub-terrain row each env is on
  - height_field            — bound HeightField when terrain_type="heightfield"
                              or "generator"

Standard usage:

    importer_cfg = TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="generator",
        num_envs=16, env_spacing=4.0,
        terrain_generator=TerrainGeneratorCfg(
            size=(8.0, 8.0), num_rows=2, num_cols=4,
            sub_terrains={"flat": flat_sub_cfg, "stairs": stairs_sub_cfg},
        ),
        max_init_terrain_level=2,
    )
    importer = TerrainImporter(importer_cfg)
    importer.spawn_into_registry()         # publish to spawner registry
    origins = importer.env_origins         # per-env world origin
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .terrain_generator import (
    HeightField,
    discrete_obstacles_terrain,
    flat_terrain,
    pyramid_sloped_terrain,
    pyramid_stairs_terrain,
    random_uniform_terrain,
    stepping_stones_terrain,
)


# ────────────────────────────────────────────────────────────────────────────
# TerrainSubTerrainCfg — one sub-terrain "tile" in a generator grid
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class TerrainSubTerrainCfg:
    """One sub-terrain entry in the generator grid.

    `function` is a builder name from `isaaclab.terrains.terrain_generator`:
      "flat" / "random_uniform" / "pyramid_stairs" / "pyramid_sloped" /
      "stepping_stones" / "discrete_obstacles"

    `proportion` weights random sub-terrain selection per cell (rows are
    sampled by curriculum level; cols within a row are sampled by
    proportion). `params` is forwarded as kwargs to the builder.
    """
    function: str = "flat"
    proportion: float = 1.0
    params: dict = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────────────
# TerrainGeneratorCfg
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class TerrainGeneratorCfg:
    """Cfg for assembling a grid of sub-terrains.

    `size = (sx, sy)` is the size of ONE sub-terrain tile (meters).
    `num_rows` = curriculum levels (rows of progressively harder terrains).
    `num_cols` = environment instances per level.

    `sub_terrains` is a dict {name → TerrainSubTerrainCfg}. The importer
    samples sub-terrains per cell weighted by `proportion`.

    `difficulty_range` is forwarded into the builder when applicable
    (currently a stub; the iter 21 generators don't yet take difficulty).
    """
    size: tuple = (8.0, 8.0)
    num_rows: int = 1
    num_cols: int = 1
    horizontal_scale: float = 0.1     # meters per height-field cell
    vertical_scale: float = 0.005     # meters per int height value
    border_width: float = 1.0
    border_height: float = 0.0
    sub_terrains: Dict[str, TerrainSubTerrainCfg] = field(default_factory=dict)
    curriculum: bool = False
    difficulty_range: tuple = (0.0, 1.0)
    seed: Optional[int] = None


# Registry of builder names → callable. Each takes (rows, cols, cell_size,
# **params) and returns a HeightField. Keys mirror Isaac Lab.
_BUILDERS: Dict[str, Callable] = {
    "flat": flat_terrain,
    "random_uniform": random_uniform_terrain,
    "pyramid_stairs": pyramid_stairs_terrain,
    "pyramid_sloped": pyramid_sloped_terrain,
    "stepping_stones": stepping_stones_terrain,
    "discrete_obstacles": discrete_obstacles_terrain,
}


# ────────────────────────────────────────────────────────────────────────────
# TerrainImporterCfg + TerrainImporter
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class TerrainImporterCfg:
    """Mirror of `isaaclab.terrains.TerrainImporterCfg`."""
    prim_path: str = "/World/ground"
    terrain_type: str = "plane"
    num_envs: int = 1
    env_spacing: float = 4.0
    terrain_generator: Optional[TerrainGeneratorCfg] = None
    height_field: Optional[HeightField] = None
    usd_path: str = ""
    max_init_terrain_level: int = 0
    # Friction / restitution forwarded for API parity (host-consumed).
    physics_material: dict = field(default_factory=dict)


class TerrainImporter:
    """Declarative terrain importer with per-env origin grid + curriculum.

    Construction:
      1. Validate terrain_type
      2. Build / bind the terrain (heightfield or proxy)
      3. Compute per-env origins (grid layout)
      4. Initialize curriculum state

    The actual mesh / heightfield is bound to `self.height_field` (when
    applicable). Downstream code reads:
      - self.env_origins         — list of (x, y, z) per env
      - self.terrain_levels      — list[int] per env (curriculum level)
      - self.terrain_types       — list[int] per env (sub-terrain row)
      - self.height_field        — bound HeightField (or None)
    """

    cfg: TerrainImporterCfg

    def __init__(self, cfg: TerrainImporterCfg):
        # Validate.
        if cfg.terrain_type not in ("plane", "heightfield", "generator", "usd"):
            raise ValueError(
                f"terrain_type must be one of plane/heightfield/generator/usd; "
                f"got {cfg.terrain_type!r}"
            )
        if cfg.num_envs <= 0:
            raise ValueError(f"num_envs must be > 0; got {cfg.num_envs}")

        self.cfg = cfg
        self.height_field: Optional[HeightField] = None
        self._sub_terrain_grid: Optional[List[List[str]]] = None
        self.env_origins: List[tuple] = []
        self.terrain_levels: List[int] = [0] * cfg.num_envs
        self.terrain_types: List[int] = [0] * cfg.num_envs

        # Build / bind terrain.
        if cfg.terrain_type == "plane":
            pass  # nothing to do; infinite flat ground
        elif cfg.terrain_type == "heightfield":
            if cfg.height_field is None:
                raise ValueError(
                    "terrain_type='heightfield' requires height_field= in cfg"
                )
            self.height_field = cfg.height_field
        elif cfg.terrain_type == "generator":
            if cfg.terrain_generator is None:
                raise ValueError(
                    "terrain_type='generator' requires terrain_generator= in cfg"
                )
            if not cfg.terrain_generator.sub_terrains:
                raise ValueError(
                    "TerrainGeneratorCfg.sub_terrains must be non-empty"
                )
            self._build_generator()
        elif cfg.terrain_type == "usd":
            if not cfg.usd_path:
                raise ValueError("terrain_type='usd' requires usd_path in cfg")
            # We don't load USD here; just record. A downstream USD parser
            # will read self.cfg.usd_path on spawn_into_registry().

        # Compute per-env origins.
        self.env_origins = self._compute_env_origins()

    # ── generator-mode terrain build ─────────────────────────────────────

    def _build_generator(self) -> None:
        """Assemble a (num_rows, num_cols) grid of sub-terrains into a
        single HeightField, plus track which sub-terrain is in each cell."""
        gen: TerrainGeneratorCfg = self.cfg.terrain_generator  # type: ignore[assignment]
        # Sub-terrain selection per (row, col). Rows = difficulty levels
        # (curriculum); cols = env instances at that level. Use proportion-
        # weighted selection driven by a deterministic LCG when seed set.
        from ..algos.cem import _Lcg
        rng = _Lcg(gen.seed if gen.seed is not None else 0)
        names = list(gen.sub_terrains.keys())
        weights = [gen.sub_terrains[n].proportion for n in names]
        wsum = sum(weights)
        if wsum <= 0.0:
            raise ValueError("sub_terrain proportions sum to 0")
        cum = [w / wsum for w in weights]
        for i in range(1, len(cum)):
            cum[i] += cum[i - 1]

        grid: List[List[str]] = [[""] * gen.num_cols for _ in range(gen.num_rows)]
        for r in range(gen.num_rows):
            for c in range(gen.num_cols):
                u = rng.next_u01()
                pick = next(
                    (n for n, ct in zip(names, cum) if u < ct), names[-1]
                )
                grid[r][c] = pick
        self._sub_terrain_grid = grid

        # Assemble the full HeightField by stitching per-cell sub-fields.
        # Each sub-terrain tile is (size_x / horizontal_scale) cells wide.
        cells_per_tile_x = max(1, int(round(gen.size[0] / gen.horizontal_scale)))
        cells_per_tile_y = max(1, int(round(gen.size[1] / gen.horizontal_scale)))
        total_cols = cells_per_tile_x * gen.num_cols
        total_rows = cells_per_tile_y * gen.num_rows

        # Build a single big HeightField row by row.
        full_heights: List[List[float]] = [
            [0.0] * total_cols for _ in range(total_rows)
        ]
        for r in range(gen.num_rows):
            for c in range(gen.num_cols):
                name = grid[r][c]
                sub_cfg = gen.sub_terrains[name]
                builder = _BUILDERS.get(sub_cfg.function)
                if builder is None:
                    raise KeyError(
                        f"sub_terrain function '{sub_cfg.function}' not in "
                        f"{sorted(_BUILDERS.keys())}"
                    )
                # Call with positional / keyword as builder accepts. The
                # iter 21 builders all share (rows, cols, cell_size, **params).
                sub_hf = builder(
                    rows=cells_per_tile_y, cols=cells_per_tile_x,
                    cell_size=gen.horizontal_scale, **sub_cfg.params,
                )
                # Copy into the full grid.
                r_off = r * cells_per_tile_y
                c_off = c * cells_per_tile_x
                for rr in range(cells_per_tile_y):
                    for cc in range(cells_per_tile_x):
                        full_heights[r_off + rr][c_off + cc] = (
                            sub_hf.height_at(rr, cc)
                        )

        self.height_field = HeightField(
            rows=total_rows, cols=total_cols,
            cell_size=gen.horizontal_scale,
            heights=full_heights,
        )

    # ── env origin grid ──────────────────────────────────────────────────

    def _compute_env_origins(self) -> List[tuple]:
        """Compute per-env world-frame (x, y, z) origin.

        For "plane" / "heightfield" / "usd": square grid centred at origin
        with `env_spacing` between cells.

        For "generator": one env per (row, col) cell of the sub-terrain
        grid; origin lives at the centre of each cell, with the cell's
        height (centre cell) folded into z.
        """
        n = self.cfg.num_envs
        if self.cfg.terrain_type == "generator":
            gen: TerrainGeneratorCfg = self.cfg.terrain_generator  # type: ignore[assignment]
            origins: List[tuple] = []
            sx, sy = gen.size
            half_x = (gen.num_cols - 1) * sx * 0.5
            half_y = (gen.num_rows - 1) * sy * 0.5
            for i in range(n):
                # Tile rows/cols cycle modulo grid; default level 0 = row 0
                # (the cfg.max_init_terrain_level can override below).
                row = self.terrain_levels[i]
                col = i % gen.num_cols
                if row >= gen.num_rows:
                    row = gen.num_rows - 1
                self.terrain_levels[i] = row
                self.terrain_types[i] = row  # sub-terrain row index
                x = col * sx - half_x
                y = row * sy - half_y
                origins.append((x, y, 0.0))
            return origins

        # Plane / heightfield / usd: square grid, near-square root.
        # num_per_row = ceil(sqrt(n))
        import math
        per_row = max(1, int(math.ceil(math.sqrt(n))))
        spacing = self.cfg.env_spacing
        half = (per_row - 1) * spacing * 0.5
        origins = []
        for i in range(n):
            r = i // per_row
            c = i % per_row
            origins.append((c * spacing - half, r * spacing - half, 0.0))
        return origins

    # ── spawn into registry ──────────────────────────────────────────────

    def spawn_into_registry(self) -> Optional[Any]:
        """Push a terrain SpawnedPrim onto the active spawner registry.

        For "plane": records a large CuboidCfg (thin ground plate).
        For "heightfield" / "generator": records a custom kind="terrain"
        prim carrying the HeightField in extras.
        For "usd": records via UsdFileCfg.
        """
        from ..sim.spawners import (
            CuboidCfg, UsdFileCfg, spawn_cuboid, spawn_from_usd,
        )
        from ..sim.spawners.spawner import SpawnedPrim, get_registry

        cfg = self.cfg
        if cfg.terrain_type == "plane":
            # 100m × 100m × 0.1m ground plate at z=-0.05 (top at z=0).
            return spawn_cuboid(
                cfg.prim_path,
                CuboidCfg(size=(100.0, 100.0, 0.1), color=(0.5, 0.5, 0.5)),
                translation=(0.0, 0.0, -0.05),
            )

        if cfg.terrain_type == "usd":
            return spawn_from_usd(
                cfg.prim_path, UsdFileCfg(usd_path=cfg.usd_path),
            )

        # heightfield / generator: custom kind="terrain"
        prim = SpawnedPrim(
            path=cfg.prim_path, kind="terrain", cfg=cfg,
            extras={
                "height_field": self.height_field,
                "sub_terrain_grid": self._sub_terrain_grid,
            },
        )
        get_registry().add(prim)
        return prim

    # ── curriculum API ───────────────────────────────────────────────────

    def update_env_origins(
        self,
        env_ids: List[int],
        level_deltas: Optional[List[int]] = None,
    ) -> None:
        """Advance / regress per-env curriculum level.

        `level_deltas[i]` is added to `terrain_levels[env_ids[i]]` (clamped
        to [0, num_rows-1] for generator mode). When `level_deltas` is None
        all envs in `env_ids` advance by +1.
        """
        if level_deltas is None:
            level_deltas = [1] * len(env_ids)
        if len(level_deltas) != len(env_ids):
            raise ValueError(
                f"level_deltas length {len(level_deltas)} != env_ids length {len(env_ids)}"
            )
        num_rows = (
            self.cfg.terrain_generator.num_rows
            if (self.cfg.terrain_type == "generator" and self.cfg.terrain_generator is not None)
            else 1
        )
        for i, env_idx in enumerate(env_ids):
            new_level = self.terrain_levels[env_idx] + level_deltas[i]
            self.terrain_levels[env_idx] = max(0, min(num_rows - 1, new_level))
        # Recompute origins (positions may shift in generator mode).
        self.env_origins = self._compute_env_origins()

    def get_env_origin(self, env_idx: int) -> tuple:
        return self.env_origins[env_idx]

    def get_terrain_height(self, world_x: float, world_y: float) -> float:
        """Sample heightfield elevation at a world-frame point. Returns 0
        for terrain_type=plane or when out of bounds (heightfield-bound)."""
        if self.height_field is None:
            return 0.0
        hf = self.height_field
        cell_size = hf.cell_size
        rows = hf.rows
        cols = hf.cols
        col_f = (world_x / cell_size) + (cols - 1) * 0.5
        row_f = (world_y / cell_size) + (rows - 1) * 0.5
        col = max(0, min(cols - 1, int(round(col_f))))
        row = max(0, min(rows - 1, int(round(row_f))))
        return hf.height_at(row, col)
