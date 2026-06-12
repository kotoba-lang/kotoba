"""isaaclab.sim.spawners — declarative USD prim factories.

Mirror of `isaaclab.sim.spawners` (Isaac Lab 1.x). Every Isaac Lab example
declares scene geometry via cfg dataclasses (CuboidCfg, SphereCfg, …)
then calls `sim_utils.spawn_*(prim_path, cfg, ...)` to materialize the
prim on the active USD Stage.

In upstream Isaac Lab the spawners instantiate UsdGeom prims via pxr.Usd.
In the nv_compat surface — where the host wires up its own renderer —
spawners record per-prim requests into a `SpawnedPrimRegistry` (lightweight
collector). A downstream viewport / debug-renderer subscriber reads the
registry and instantiates real prims on whatever Stage backend the host
uses.

Surface:

  shapes:
    - CuboidCfg / spawn_cuboid       — axis-aligned box; size = (X, Y, Z)
    - SphereCfg / spawn_sphere       — sphere with radius
    - CylinderCfg / spawn_cylinder   — capped cylinder; radius + height
    - ConeCfg / spawn_cone           — cone; radius + height
    - CapsuleCfg / spawn_capsule     — capped cylinder with hemispherical ends

  lights:
    - DistantLightCfg / spawn_light  — directional (sun) light; intensity + color
    - DomeLightCfg                   — image-based skydome
    - SphereLightCfg                 — omni point light; intensity + radius

  from_files:
    - UsdFileCfg / spawn_from_usd    — load .usd / .usda / .urdf onto the stage

  registry:
    - SpawnerCfgBase                 — common base for every cfg
    - SpawnedPrim                    — one prim record (path / kind / cfg /
                                       pose / extras)
    - SpawnedPrimRegistry            — module-level singleton collector;
                                       `get_registry()` returns the active
                                       one (host swaps via push/pop)
    - push_registry / pop_registry   — context-manager-friendly stack

Standard usage:

    from kotodama.nv_compat.isaaclab.sim.spawners import (
        CuboidCfg, SphereCfg, spawn_cuboid, spawn_sphere,
        get_registry,
    )

    spawn_cuboid("/World/box", CuboidCfg(size=(0.1, 0.2, 0.3)))
    spawn_sphere("/World/ball", SphereCfg(radius=0.05),
                  translation=(0.5, 0.0, 0.1))

    for prim in get_registry().prims():
        print(prim.path, prim.kind, prim.cfg.size if hasattr(prim.cfg, "size") else None)
"""

from .from_files import UsdFileCfg, spawn_from_usd
from .lights import (
    DistantLightCfg,
    DomeLightCfg,
    SphereLightCfg,
    spawn_light,
)
from .shapes import (
    CapsuleCfg,
    ConeCfg,
    CuboidCfg,
    CylinderCfg,
    SphereCfg,
    spawn_capsule,
    spawn_cone,
    spawn_cuboid,
    spawn_cylinder,
    spawn_sphere,
)
from .spawner import (
    SpawnedPrim,
    SpawnedPrimRegistry,
    SpawnerCfgBase,
    get_registry,
    pop_registry,
    push_registry,
)

__all__ = [
    # registry
    "SpawnerCfgBase", "SpawnedPrim", "SpawnedPrimRegistry",
    "get_registry", "push_registry", "pop_registry",
    # shapes
    "CuboidCfg", "SphereCfg", "CylinderCfg", "ConeCfg", "CapsuleCfg",
    "spawn_cuboid", "spawn_sphere", "spawn_cylinder",
    "spawn_cone", "spawn_capsule",
    # lights
    "DistantLightCfg", "DomeLightCfg", "SphereLightCfg",
    "spawn_light",
    # from_files
    "UsdFileCfg", "spawn_from_usd",
]
