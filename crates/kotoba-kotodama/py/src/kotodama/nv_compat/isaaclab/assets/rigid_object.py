"""RigidObject — single-body rigid prim wrapper.

Mirror of `isaaclab.assets.RigidObject`. Tracks root pose + velocity for
a free-flying rigid body; primarily used for non-articulated props
(boxes, balls, cylinders) on the stage.

In upstream Isaac Lab the RigidObject reads physics state from PhysX. In
the nv_compat surface where physics is host-supplied, the object exposes
read/write APIs and a Euler-integration `update()` so simple ballistic
behavior is testable end-to-end.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .asset_base import AssetBase, AssetBaseCfg, AssetBaseInitialStateCfg


@dataclass
class RigidObjectInitialStateCfg(AssetBaseInitialStateCfg):
    """Same as AssetBaseInitialStateCfg — no rigid-specific fields beyond
    pose + velocity."""


@dataclass
class RigidObjectCfg(AssetBaseCfg):
    """Mirror of `isaaclab.assets.RigidObjectCfg`.

    - mass:       kg (0 = static / kinematic; >0 = dynamic)
    - gravity:    when True (default), update() applies gravity each step
    - lin_damping / ang_damping: per-step velocity damping (0 = none)
    """
    init_state: RigidObjectInitialStateCfg = field(
        default_factory=RigidObjectInitialStateCfg
    )
    mass: float = 1.0
    gravity: bool = True
    gravity_vec: tuple = (0.0, 0.0, -9.81)
    lin_damping: float = 0.0
    ang_damping: float = 0.0


class RigidObjectData:
    """Read-only data view exposed via RigidObject.data."""

    def __init__(self, ro: "RigidObject"):
        self._ro = ro

    @property
    def root_pos_w(self) -> tuple:
        return self._ro.root_position

    @property
    def root_quat_w(self) -> tuple:
        return self._ro.root_orientation

    @property
    def root_lin_vel_w(self) -> tuple:
        return self._ro.root_linear_velocity

    @property
    def root_ang_vel_w(self) -> tuple:
        return self._ro.root_angular_velocity


class RigidObject(AssetBase):
    """Single-body rigid prim wrapper.

    `update(physics_dt)` does forward-Euler integration of the root pose
    using current root_velocity + (optionally) gravity acceleration. Simple
    enough for prop tracking; non-rigid-body collision is not modeled here
    (use a real physics backend for that).
    """

    cfg: RigidObjectCfg

    def __init__(self, cfg: RigidObjectCfg):
        if cfg.mass < 0:
            raise ValueError(f"mass must be non-negative; got {cfg.mass}")
        super().__init__(cfg)
        self.data = RigidObjectData(self)

    # ── per-step integration ─────────────────────────────────────────────

    def update(self, physics_dt: float) -> None:
        """Forward-Euler step: pos += vel*dt; lin_vel += g*dt (when gravity
        enabled + mass > 0); apply damping."""
        cfg: RigidObjectCfg = self.cfg  # type: ignore[assignment]
        # Skip integration for static objects.
        if cfg.mass <= 0.0:
            return
        # Apply gravity to lin_vel.
        if cfg.gravity:
            lv = list(self._root_lin_vel)
            for i in range(3):
                lv[i] += cfg.gravity_vec[i] * physics_dt
            self._root_lin_vel = tuple(lv)
        # Apply damping.
        if cfg.lin_damping > 0.0:
            f = max(0.0, 1.0 - cfg.lin_damping * physics_dt)
            lv = self._root_lin_vel
            self._root_lin_vel = (lv[0] * f, lv[1] * f, lv[2] * f)
        if cfg.ang_damping > 0.0:
            f = max(0.0, 1.0 - cfg.ang_damping * physics_dt)
            av = self._root_ang_vel
            self._root_ang_vel = (av[0] * f, av[1] * f, av[2] * f)
        # Integrate position.
        pos = self._root_pos
        lv = self._root_lin_vel
        self._root_pos = (
            pos[0] + lv[0] * physics_dt,
            pos[1] + lv[1] * physics_dt,
            pos[2] + lv[2] * physics_dt,
        )
        # Angular integration of orientation is omitted (would need quat
        # exponential for small-angle integration; not needed for the
        # simple prop tracking use case).
