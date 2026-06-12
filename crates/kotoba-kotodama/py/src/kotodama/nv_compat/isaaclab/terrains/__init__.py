"""isaaclab.terrains — procedural height-field generators for legged locomotion.

Mirrors `omni.isaac.lab.terrains` (Isaac Lab 1.x). Each generator returns a
HeightField (cells × cells × scalar) that downstream scene consumers (Camera
shadow casting, Lidar raycast, articulation collision queries) can integrate
once kami-render WGSL lands.

Provided terrain types (R1.x scope):
  - flat                  — constant elevation (baseline)
  - random_uniform        — uniform noise heights (locomotion robustness)
  - pyramid_stairs        — concentric stair rings (climbing curriculum)
  - pyramid_sloped        — radial inclined surface (slope locomotion)
  - stepping_stones       — sparse raised circles (foothold precision)
  - discrete_obstacles    — random raised boxes (obstacle avoidance)

TerrainImporter:
  - TerrainImporterCfg / TerrainImporter — declarative terrain loader
    (plane/heightfield/generator/usd); composes per-env origin grid for
    parallel envs + curriculum-level tracking for legged-locomotion
    training.
  - TerrainGeneratorCfg / TerrainSubTerrainCfg — grid of sub-terrains
    assembled from the above generators.

stdlib-only.
"""

from .importer import (
    TerrainGeneratorCfg,
    TerrainImporter,
    TerrainImporterCfg,
    TerrainSubTerrainCfg,
)
from .terrain_generator import (
    HeightField,
    discrete_obstacles_terrain,
    flat_terrain,
    pyramid_sloped_terrain,
    pyramid_stairs_terrain,
    random_uniform_terrain,
    stepping_stones_terrain,
)

__all__ = [
    "HeightField",
    "flat_terrain",
    "random_uniform_terrain",
    "pyramid_stairs_terrain",
    "pyramid_sloped_terrain",
    "stepping_stones_terrain",
    "discrete_obstacles_terrain",
    "TerrainImporterCfg", "TerrainImporter",
    "TerrainGeneratorCfg", "TerrainSubTerrainCfg",
]
