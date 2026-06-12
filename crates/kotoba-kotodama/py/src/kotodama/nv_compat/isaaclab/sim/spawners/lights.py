"""Light spawners — DistantLight / DomeLight / SphereLight.

Mirror of `isaaclab.sim.spawners.lights`. Each cfg corresponds to a UsdLux
prim type in upstream Isaac Lab; in nv_compat they're recorded as
SpawnedPrim entries with kind="light" + a per-cfg `light_kind` field
("distant" / "dome" / "sphere").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .spawner import SpawnedPrim, SpawnerCfgBase, get_registry


@dataclass
class DistantLightCfg(SpawnerCfgBase):
    """Directional (sun-like) light. `intensity` in candela/m² (UsdLux convention).
    Default direction is the prim's local -z (matches UsdLux DistantLight)."""
    intensity: float = 1000.0
    angle: float = 0.53      # degrees, sun-disk angular size
    light_kind: str = "distant"


@dataclass
class DomeLightCfg(SpawnerCfgBase):
    """Image-based skydome light. `texture_path` is an HDR image identifier;
    when empty, the dome emits uniform `color * intensity`."""
    intensity: float = 1000.0
    texture_path: str = ""
    light_kind: str = "dome"


@dataclass
class SphereLightCfg(SpawnerCfgBase):
    """Omni point light. Falls off as 1/r²; `radius` controls soft-shadow size."""
    intensity: float = 1000.0
    radius: float = 0.1
    light_kind: str = "sphere"


def spawn_light(prim_path: str, cfg: Any,
                translation: tuple = (0.0, 0.0, 0.0),
                orientation: tuple = (0.0, 0.0, 0.0, 1.0)) -> SpawnedPrim:
    """Spawn any light cfg (Distant/Dome/Sphere). Records with kind="light";
    the specific shape is in `cfg.light_kind`."""
    if not prim_path:
        raise ValueError("prim_path is required")
    if not hasattr(cfg, "light_kind"):
        raise TypeError(
            f"spawn_light: cfg must have `light_kind`; "
            f"got {type(cfg).__name__} (use DistantLightCfg / DomeLightCfg / SphereLightCfg)"
        )
    prim = SpawnedPrim(
        path=prim_path, kind="light", cfg=cfg,
        translation=tuple(translation), orientation=tuple(orientation),
    )
    get_registry().add(prim)
    return prim
