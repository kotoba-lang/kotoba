"""AssetBase — common base for RigidObject + Articulation.

Holds the cfg-driven invariants (prim_path / spawn cfg / initial pose),
manages the connection to the spawner registry, and exposes the lifecycle
hooks the subclasses extend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AssetBaseInitialStateCfg:
    """Common initial-state fields shared by every asset type.

    `pos` + `rot` are root-pose in world frame (quat = (x, y, z, w)).
    `lin_vel` + `ang_vel` are root-velocity. Subclasses extend with type-
    specific fields (Articulation adds joint_pos / joint_vel).
    """
    pos: tuple = (0.0, 0.0, 0.0)
    rot: tuple = (0.0, 0.0, 0.0, 1.0)
    lin_vel: tuple = (0.0, 0.0, 0.0)
    ang_vel: tuple = (0.0, 0.0, 0.0)


@dataclass
class AssetBaseCfg:
    """Mirror of `isaaclab.assets.AssetBaseCfg`.

    `prim_path` — USD path the asset is spawned at.
    `spawn`     — spawner cfg (UsdFileCfg, CuboidCfg, …); when None the
                  asset wraps an already-existing prim (rare).
    `init_state` — initial state at reset time.
    `debug_vis` — request to spawn debug visualization markers (consumed
                  by downstream viewport — recorded on the asset).
    """
    prim_path: str = ""
    spawn: Any = None
    init_state: AssetBaseInitialStateCfg = field(
        default_factory=AssetBaseInitialStateCfg
    )
    debug_vis: bool = False


class AssetBase:
    """Common base for stateful Isaac Lab assets.

    Subclasses extend with type-specific data (joint state for Articulation,
    rigid pose for RigidObject) but share the lifecycle:

      __init__(cfg)            — validate cfg, set up internal buffers
      spawn_into_registry()    — push the cfg.spawn onto the active
                                  spawner registry (idempotent on
                                  prim_path)
      reset()                  — restore internal state to cfg.init_state
      update(physics_dt)       — per-step hook (subclass may override for
                                  integration; base is no-op)
    """

    def __init__(self, cfg: AssetBaseCfg):
        if not cfg.prim_path:
            raise ValueError(
                f"{type(self).__name__}.cfg.prim_path is required"
            )
        self.cfg = cfg
        # Root pose / velocity buffers (latest known values).
        self._root_pos: tuple = tuple(cfg.init_state.pos)
        self._root_quat: tuple = tuple(cfg.init_state.rot)
        self._root_lin_vel: tuple = tuple(cfg.init_state.lin_vel)
        self._root_ang_vel: tuple = tuple(cfg.init_state.ang_vel)
        self._is_initialized: bool = False

    # ── public lifecycle ─────────────────────────────────────────────────

    def spawn_into_registry(self) -> Optional[Any]:
        """Push self.cfg.spawn onto the active spawner registry at
        self.cfg.prim_path. Idempotent (re-spawning replaces). Returns
        the SpawnedPrim record (or None when cfg.spawn is None).
        """
        if self.cfg.spawn is None:
            return None
        # Lazy-import to avoid circular dep at module load time.
        from ..sim.spawners import (
            CuboidCfg, SphereCfg, CylinderCfg, ConeCfg, CapsuleCfg,
            DistantLightCfg, DomeLightCfg, SphereLightCfg,
            UsdFileCfg,
            spawn_cuboid, spawn_sphere, spawn_cylinder, spawn_cone, spawn_capsule,
            spawn_light, spawn_from_usd,
        )
        cfg = self.cfg.spawn
        path = self.cfg.prim_path
        pos = self._root_pos
        rot = self._root_quat
        if isinstance(cfg, CuboidCfg):
            return spawn_cuboid(path, cfg, translation=pos, orientation=rot)
        if isinstance(cfg, SphereCfg):
            return spawn_sphere(path, cfg, translation=pos, orientation=rot)
        if isinstance(cfg, CylinderCfg):
            return spawn_cylinder(path, cfg, translation=pos, orientation=rot)
        if isinstance(cfg, ConeCfg):
            return spawn_cone(path, cfg, translation=pos, orientation=rot)
        if isinstance(cfg, CapsuleCfg):
            return spawn_capsule(path, cfg, translation=pos, orientation=rot)
        if isinstance(cfg, (DistantLightCfg, DomeLightCfg, SphereLightCfg)):
            return spawn_light(path, cfg, translation=pos, orientation=rot)
        if isinstance(cfg, UsdFileCfg):
            return spawn_from_usd(path, cfg, translation=pos, orientation=rot)
        raise TypeError(
            f"{type(self).__name__}.cfg.spawn must be a SpawnerCfgBase subclass; "
            f"got {type(cfg).__name__}"
        )

    def reset(self) -> None:
        """Restore root pose + velocity to cfg.init_state. Subclasses
        override + chain via super().reset() to also reset their type-
        specific state (joint_pos for Articulation, …)."""
        self._root_pos = tuple(self.cfg.init_state.pos)
        self._root_quat = tuple(self.cfg.init_state.rot)
        self._root_lin_vel = tuple(self.cfg.init_state.lin_vel)
        self._root_ang_vel = tuple(self.cfg.init_state.ang_vel)
        self._is_initialized = True

    def update(self, physics_dt: float) -> None:
        """Per-step integration hook. Default no-op; subclasses may extend."""
        pass

    # ── root pose accessors ──────────────────────────────────────────────

    @property
    def root_position(self) -> tuple:
        return self._root_pos

    @property
    def root_orientation(self) -> tuple:
        return self._root_quat

    @property
    def root_linear_velocity(self) -> tuple:
        return self._root_lin_vel

    @property
    def root_angular_velocity(self) -> tuple:
        return self._root_ang_vel

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized

    @property
    def prim_path(self) -> str:
        return self.cfg.prim_path

    def write_root_pose(self, pos: tuple, quat: tuple) -> None:
        """Set root pose imperatively (e.g. for reset-to-checkpoint patterns)."""
        self._root_pos = tuple(pos)
        self._root_quat = tuple(quat)

    def write_root_velocity(self, lin_vel: tuple, ang_vel: tuple) -> None:
        """Set root velocity imperatively."""
        self._root_lin_vel = tuple(lin_vel)
        self._root_ang_vel = tuple(ang_vel)
