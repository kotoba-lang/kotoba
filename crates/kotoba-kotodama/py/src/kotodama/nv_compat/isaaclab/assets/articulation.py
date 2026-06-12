"""Articulation — multi-link articulated robot wrapper.

Mirror of `isaaclab.assets.Articulation`. Wraps an `ArticulatedSystem`
parsed from URDF + stateful joint buffers + initial-state reset. The
canonical bridge between iter 42's spawners and the env physics:

  cfg = ArticulationCfg(
      prim_path="/World/cartpole",
      spawn=UsdFileCfg(urdf_text=URDF),
      init_state=ArticulationInitialStateCfg(
          pos=(0, 0, 0),
          joint_pos={"slider_to_cart": 0.0, "cart_to_pole": 0.05},
      ),
  )
  art = Articulation(cfg)
  art.reset()
  art.set_joint_effort_target([0.5])    # 1-DoF effort command
  art.update(physics_dt=1/120)

For nv_compat, the Articulation wraps the existing `_kernel.parse_urdf` +
the cartpole / double-pendulum kernels. Subclasses can override
`_physics_step()` if a different integrator is needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..._kernel import (
    ArticulatedSystem,
    CartpoleConfig,
    CartpoleState,
    DoublePendulumConfig,
    DoublePendulumState,
    cartpole_cfg_from_urdf,
    cartpole_step,
    detect_cartpole_topology,
    detect_double_pendulum_topology,
    double_pendulum_cfg_from_urdf,
    double_pendulum_step,
    parse_urdf,
)
from .asset_base import AssetBase, AssetBaseCfg, AssetBaseInitialStateCfg


# ────────────────────────────────────────────────────────────────────────────
# Initial state
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class ArticulationInitialStateCfg(AssetBaseInitialStateCfg):
    """Initial state for an Articulation.

    `joint_pos` / `joint_vel` are name → value dicts (matches Isaac Lab).
    A missing key defaults to 0 for that joint. Unknown keys are ignored
    (don't crash if URDF has more joints than the cfg lists).
    """
    joint_pos: Dict[str, float] = field(default_factory=dict)
    joint_vel: Dict[str, float] = field(default_factory=dict)


@dataclass
class ArticulationCfg(AssetBaseCfg):
    """Mirror of `isaaclab.assets.ArticulationCfg`.

    `gravity` is informational (the kernel cartpole_step already applies
    gravity from its internal config). `actuators` is a per-actuator group
    config dict — kept for API parity, consumed by iter 40 ActionTerms.
    """
    init_state: ArticulationInitialStateCfg = field(
        default_factory=ArticulationInitialStateCfg
    )
    gravity: float = 9.81
    actuators: Dict[str, Any] = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────────────
# Articulation data view
# ────────────────────────────────────────────────────────────────────────────


class ArticulationData:
    """Read-only data view exposed via Articulation.data. Mirrors the
    upstream `isaaclab.assets.ArticulationData` field set."""

    def __init__(self, art: "Articulation"):
        self._art = art

    @property
    def joint_pos(self) -> List[float]:
        return self._art.get_joint_positions()

    @property
    def joint_vel(self) -> List[float]:
        return self._art.get_joint_velocities()

    @property
    def applied_action(self) -> List[float]:
        return list(self._art._applied_action)

    @property
    def root_pos_w(self) -> tuple:
        return self._art.root_position

    @property
    def root_quat_w(self) -> tuple:
        return self._art.root_orientation


# ────────────────────────────────────────────────────────────────────────────
# Articulation
# ────────────────────────────────────────────────────────────────────────────


class Articulation(AssetBase):
    """Wraps an ArticulatedSystem from URDF + stateful joint buffers.

    Supported topologies (R1.1; matches existing kernel coverage):
      - Cartpole         (1 prismatic + 1 revolute, 2 DoF)
      - Double pendulum  (2 revolute, 2 DoF)

    For other topologies (planar n-link, 3D Featherstone), the URDF is
    still parsed and joint_pos / joint_vel buffers are allocated by joint
    count — but update() raises NotImplementedError until the kernel
    grows the matching integrator.
    """

    cfg: ArticulationCfg

    def __init__(self, cfg: ArticulationCfg):
        super().__init__(cfg)
        # Parse URDF from the spawn cfg or fail with a clear message.
        urdf_text = self._extract_urdf_text(cfg.spawn)
        if not urdf_text:
            raise ValueError(
                f"{type(self).__name__}.cfg.spawn must carry URDF text "
                f"(UsdFileCfg with urdf_text= or usd_path ending in .urdf)"
            )
        self.system: ArticulatedSystem = parse_urdf(urdf_text)
        # Joint name → index mapping.
        self.joint_names: List[str] = [j.name for j in self.system.joints]
        self.num_joints: int = len(self.joint_names)
        self._joint_pos: List[float] = [0.0] * self.num_joints
        self._joint_vel: List[float] = [0.0] * self.num_joints
        # Last applied action (effort target by default; used by mdp obs).
        self._applied_action: List[float] = [0.0] * self.num_joints
        # Detect topology + build kernel cfg.
        self._kind: str
        self._cp_state: Optional[CartpoleState] = None
        self._cp_cfg: Optional[CartpoleConfig] = None
        self._dp_state: Optional[DoublePendulumState] = None
        self._dp_cfg: Optional[DoublePendulumConfig] = None
        if detect_cartpole_topology(self.system):
            self._kind = "cartpole"
            self._cp_state = CartpoleState()
            self._cp_cfg = cartpole_cfg_from_urdf(
                self.system, gravity=cfg.gravity, dt=1.0 / 120.0,
            )
        elif detect_double_pendulum_topology(self.system):
            self._kind = "double_pendulum"
            self._dp_state = DoublePendulumState()
            self._dp_cfg = double_pendulum_cfg_from_urdf(
                self.system, gravity=cfg.gravity, dt=1.0 / 120.0,
            )
        else:
            self._kind = "generic"
        # Public data view.
        self.data = ArticulationData(self)

    @staticmethod
    def _extract_urdf_text(spawn: Any) -> str:
        """Pull URDF text out of a spawn cfg (UsdFileCfg or duck-typed
        equivalent). Returns "" when not available."""
        if spawn is None:
            return ""
        # UsdFileCfg.urdf_text takes precedence.
        if hasattr(spawn, "urdf_text") and spawn.urdf_text:
            return spawn.urdf_text
        # Else try to read from usd_path if it ends in .urdf.
        path = getattr(spawn, "usd_path", "")
        if path.endswith(".urdf"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except OSError:
                pass
        return ""

    # ── reset ────────────────────────────────────────────────────────────

    def reset(self) -> None:
        super().reset()
        cfg: ArticulationCfg = self.cfg  # type: ignore[assignment]
        # Apply cfg.init_state.joint_pos by joint name.
        for i, name in enumerate(self.joint_names):
            self._joint_pos[i] = float(cfg.init_state.joint_pos.get(name, 0.0))
            self._joint_vel[i] = float(cfg.init_state.joint_vel.get(name, 0.0))
        self._applied_action = [0.0] * self.num_joints
        # Mirror joint state into the kernel state buffers.
        if self._kind == "cartpole" and self._cp_state is not None:
            self._cp_state = CartpoleState(
                x=self._joint_pos[0] if self.num_joints > 0 else 0.0,
                x_dot=self._joint_vel[0] if self.num_joints > 0 else 0.0,
                theta=self._joint_pos[1] if self.num_joints > 1 else 0.0,
                theta_dot=self._joint_vel[1] if self.num_joints > 1 else 0.0,
            )
        elif self._kind == "double_pendulum" and self._dp_state is not None:
            self._dp_state = DoublePendulumState(
                q1=self._joint_pos[0] if self.num_joints > 0 else 0.0,
                q1_dot=self._joint_vel[0] if self.num_joints > 0 else 0.0,
                q2=self._joint_pos[1] if self.num_joints > 1 else 0.0,
                q2_dot=self._joint_vel[1] if self.num_joints > 1 else 0.0,
            )

    # ── public state accessors (used by mdp obs terms) ──────────────────

    def get_joint_positions(self) -> List[float]:
        # Pull from kernel state when available (kernel may have evolved).
        if self._kind == "cartpole" and self._cp_state is not None:
            return [self._cp_state.x, self._cp_state.theta]
        if self._kind == "double_pendulum" and self._dp_state is not None:
            return [self._dp_state.q1, self._dp_state.q2]
        return list(self._joint_pos)

    def get_joint_velocities(self) -> List[float]:
        if self._kind == "cartpole" and self._cp_state is not None:
            return [self._cp_state.x_dot, self._cp_state.theta_dot]
        if self._kind == "double_pendulum" and self._dp_state is not None:
            return [self._dp_state.q1_dot, self._dp_state.q2_dot]
        return list(self._joint_vel)

    def set_joint_positions(self, positions: List[float]) -> None:
        for i in range(min(len(positions), self.num_joints)):
            self._joint_pos[i] = float(positions[i])
        # Mirror to kernel state.
        if self._kind == "cartpole" and self._cp_state is not None:
            if self.num_joints > 0:
                self._cp_state.x = self._joint_pos[0]
            if self.num_joints > 1:
                self._cp_state.theta = self._joint_pos[1]
        elif self._kind == "double_pendulum" and self._dp_state is not None:
            if self.num_joints > 0:
                self._dp_state.q1 = self._joint_pos[0]
            if self.num_joints > 1:
                self._dp_state.q2 = self._joint_pos[1]

    def set_joint_velocities(self, velocities: List[float]) -> None:
        for i in range(min(len(velocities), self.num_joints)):
            self._joint_vel[i] = float(velocities[i])
        if self._kind == "cartpole" and self._cp_state is not None:
            if self.num_joints > 0:
                self._cp_state.x_dot = self._joint_vel[0]
            if self.num_joints > 1:
                self._cp_state.theta_dot = self._joint_vel[1]
        elif self._kind == "double_pendulum" and self._dp_state is not None:
            if self.num_joints > 0:
                self._dp_state.q1_dot = self._joint_vel[0]
            if self.num_joints > 1:
                self._dp_state.q2_dot = self._joint_vel[1]

    # ── action injection (matches the mdp.actions contract) ────────────

    def set_joint_effort_target(self, effort: List[float]) -> None:
        """Stash effort vector for the next update() to consume."""
        for i in range(min(len(effort), self.num_joints)):
            self._applied_action[i] = float(effort[i])

    # ── physics step ─────────────────────────────────────────────────────

    def update(self, physics_dt: float) -> None:
        """Advance kernel state by `physics_dt` using the stashed action."""
        if self._kind == "cartpole" and self._cp_cfg is not None and self._cp_state is not None:
            cfg = CartpoleConfig(
                cart_mass=self._cp_cfg.cart_mass,
                pole_mass=self._cp_cfg.pole_mass,
                pole_half_length=self._cp_cfg.pole_half_length,
                gravity=self._cp_cfg.gravity,
                force_mag=self._cp_cfg.force_mag,
                dt=physics_dt,
            )
            force = self._applied_action[0] if self._applied_action else 0.0
            cartpole_step(self._cp_state, force, cfg)
            return
        if self._kind == "double_pendulum" and self._dp_cfg is not None and self._dp_state is not None:
            cfg = DoublePendulumConfig(
                l1=self._dp_cfg.l1, l2=self._dp_cfg.l2,
                m1=self._dp_cfg.m1, m2=self._dp_cfg.m2,
                gravity=self._dp_cfg.gravity, dt=physics_dt,
            )
            t1 = self._applied_action[0] if len(self._applied_action) > 0 else 0.0
            t2 = self._applied_action[1] if len(self._applied_action) > 1 else 0.0
            double_pendulum_step(self._dp_state, (t1, t2), cfg)
            return
        # Generic / unsupported.
        raise NotImplementedError(
            f"Articulation.update() not implemented for topology '{self._kind}'; "
            f"supported: cartpole, double_pendulum"
        )

    # ── env-integration helper ──────────────────────────────────────────

    def joint_name_to_index(self, name: str) -> int:
        try:
            return self.joint_names.index(name)
        except ValueError:
            raise KeyError(
                f"joint '{name}' not in URDF; have: {self.joint_names}"
            ) from None
