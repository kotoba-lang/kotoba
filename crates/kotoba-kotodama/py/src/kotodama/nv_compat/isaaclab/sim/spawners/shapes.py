"""Shape spawners — Cuboid / Sphere / Cylinder / Cone / Capsule.

Each spawn_* function constructs a `SpawnedPrim` from the cfg + pose args
and appends it to the active registry. Idempotent on prim path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .spawner import SpawnedPrim, SpawnerCfgBase, get_registry


# ────────────────────────────────────────────────────────────────────────────
# Cfgs
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class CuboidCfg(SpawnerCfgBase):
    """Axis-aligned box. `size = (X, Y, Z)` extents in meters."""
    size: tuple = (0.1, 0.1, 0.1)


@dataclass
class SphereCfg(SpawnerCfgBase):
    """Sphere primitive. `radius` in meters."""
    radius: float = 0.05


@dataclass
class CylinderCfg(SpawnerCfgBase):
    """Capped cylinder. `radius` + `height` in meters; axis = local +z."""
    radius: float = 0.05
    height: float = 0.1


@dataclass
class ConeCfg(SpawnerCfgBase):
    """Cone primitive. `radius` (base) + `height` in meters; apex along +z."""
    radius: float = 0.05
    height: float = 0.1


@dataclass
class CapsuleCfg(SpawnerCfgBase):
    """Capsule (capped cylinder with hemispherical ends). `radius` + `height`
    where height is the cylindrical portion only — total length is
    `height + 2*radius`."""
    radius: float = 0.05
    height: float = 0.1


# ────────────────────────────────────────────────────────────────────────────
# spawn_* functions
# ────────────────────────────────────────────────────────────────────────────


def _spawn(prim_path: str, kind: str, cfg: Any,
           translation: tuple = (0.0, 0.0, 0.0),
           orientation: tuple = (0.0, 0.0, 0.0, 1.0),
           scale: tuple = (1.0, 1.0, 1.0)) -> SpawnedPrim:
    if not prim_path:
        raise ValueError("prim_path is required")
    prim = SpawnedPrim(
        path=prim_path, kind=kind, cfg=cfg,
        translation=tuple(translation), orientation=tuple(orientation),
        scale=tuple(scale),
    )
    get_registry().add(prim)
    return prim


def spawn_cuboid(prim_path: str, cfg: CuboidCfg,
                 translation: tuple = (0.0, 0.0, 0.0),
                 orientation: tuple = (0.0, 0.0, 0.0, 1.0),
                 scale: tuple = (1.0, 1.0, 1.0)) -> SpawnedPrim:
    return _spawn(prim_path, "cuboid", cfg, translation, orientation, scale)


def spawn_sphere(prim_path: str, cfg: SphereCfg,
                 translation: tuple = (0.0, 0.0, 0.0),
                 orientation: tuple = (0.0, 0.0, 0.0, 1.0),
                 scale: tuple = (1.0, 1.0, 1.0)) -> SpawnedPrim:
    return _spawn(prim_path, "sphere", cfg, translation, orientation, scale)


def spawn_cylinder(prim_path: str, cfg: CylinderCfg,
                   translation: tuple = (0.0, 0.0, 0.0),
                   orientation: tuple = (0.0, 0.0, 0.0, 1.0),
                   scale: tuple = (1.0, 1.0, 1.0)) -> SpawnedPrim:
    return _spawn(prim_path, "cylinder", cfg, translation, orientation, scale)


def spawn_cone(prim_path: str, cfg: ConeCfg,
               translation: tuple = (0.0, 0.0, 0.0),
               orientation: tuple = (0.0, 0.0, 0.0, 1.0),
               scale: tuple = (1.0, 1.0, 1.0)) -> SpawnedPrim:
    return _spawn(prim_path, "cone", cfg, translation, orientation, scale)


def spawn_capsule(prim_path: str, cfg: CapsuleCfg,
                  translation: tuple = (0.0, 0.0, 0.0),
                  orientation: tuple = (0.0, 0.0, 0.0, 1.0),
                  scale: tuple = (1.0, 1.0, 1.0)) -> SpawnedPrim:
    return _spawn(prim_path, "capsule", cfg, translation, orientation, scale)
