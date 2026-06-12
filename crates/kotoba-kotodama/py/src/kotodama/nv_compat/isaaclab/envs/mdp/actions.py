"""Action terms — composable action processors.

Mirror of `isaaclab.envs.mdp.actions` (Isaac Lab 1.x). Action terms slice a
flat action vector into per-joint commands, optionally apply scale + offset,
and dispatch the result onto the env's articulation via one of three
control modes (effort / position / velocity).

Surface:
  - ActionTerm                    — abstract base; subclass implements
                                     `process_actions(raw)` (transform raw →
                                     processed) + `apply_actions(env)`
                                     (write the processed action onto the env)
  - JointEffortActionCfg / JointEffortAction
        — torque-control: writes scaled raw action directly to
          `env._applied_force` / `env._applied_torques` (matches the existing
          Cartpole / DoublePendulum action injection convention)
  - JointPositionActionCfg / JointPositionAction
        — position target with PD controller: writes
          K_p * (target - current) - K_d * current_vel into effort
  - JointVelocityActionCfg / JointVelocityAction
        — velocity target with P controller: writes
          K_p * (target - current_vel) into effort

ActionManager composes one or more ActionTerm into a single action vector.
`process_actions(raw)` slices `raw` by per-term offsets and dispatches each
slice to its term's process_actions. `apply_actions(env)` then triggers
every term's apply_actions in registration order — terms write into env
state which is consumed by the env's `_physics_step()` on the next sim
tick.

Standard usage:

    am = ActionManager([
        JointEffortAction(JointEffortActionCfg(joint_names=[0], scale=10.0)),
    ])
    raw_action = [0.3]                          # 1-DoF for Cartpole
    am.process_actions(raw_action)
    am.apply_actions(env)                       # writes env._applied_force
    env._physics_step()                         # consumes the action

Pure stdlib. Reuses no external state; each term carries its own buffers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ...controllers import (
    DifferentialIKController,
    DifferentialIKControllerCfg,
    OperationalSpaceController,
    OperationalSpaceControllerCfg,
)


# ────────────────────────────────────────────────────────────────────────────
# ActionTerm base
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class ActionTermCfgBase:
    """Base cfg for every ActionTerm subclass.

    `joint_names` is a list of integer joint indices (env-specific) the
    action term targets. For Cartpole the convention is `[0]` = cart slider.
    Real Isaac Lab uses joint NAME strings + regex; the nv_compat surface
    keeps it index-based for kernel-level clarity.

    `scale` multiplies the raw action element-wise; `offset` adds.
    `action_dim` is OPTIONAL — when None it's inferred from `joint_names`
    (one action element per joint). Override only for terms that want
    one action element to drive multiple joints (rare).
    """
    asset_name: str = "robot"
    joint_names: List[int] = field(default_factory=list)
    scale: float = 1.0
    offset: float = 0.0
    action_dim: Optional[int] = None


class ActionTerm:
    """Abstract base for one action processor.

    Subclasses MUST implement:
      - `apply_actions(env)`   — write `self.processed_actions` onto env
      - (optionally) `process_actions(raw)` — transform `raw` → processed

    Base provides:
      - `action_dim`           — int, computed from cfg
      - `raw_actions`          — most recent raw action slice
      - `processed_actions`    — most recent processed action (scale + offset
                                  by default; subclasses override the
                                  transformation if more is needed)
      - `reset()`              — clear buffers
    """

    cfg: ActionTermCfgBase

    def __init__(self, cfg: ActionTermCfgBase):
        self.cfg = cfg
        if not cfg.joint_names:
            raise ValueError(f"{type(self).__name__}.cfg.joint_names must be non-empty")
        self._dim: int = cfg.action_dim if cfg.action_dim is not None else len(cfg.joint_names)
        self.raw_actions: List[float] = [0.0] * self._dim
        self.processed_actions: List[float] = [0.0] * self._dim

    @property
    def action_dim(self) -> int:
        return self._dim

    @property
    def joint_names(self) -> List[int]:
        return list(self.cfg.joint_names)

    def process_actions(self, raw: List[float]) -> None:
        """Default impl: scale + offset element-wise into processed_actions."""
        if len(raw) != self._dim:
            raise ValueError(
                f"{type(self).__name__}: expected {self._dim} action elements, got {len(raw)}"
            )
        self.raw_actions = list(raw)
        s, o = self.cfg.scale, self.cfg.offset
        self.processed_actions = [r * s + o for r in raw]

    def apply_actions(self, env: Any) -> None:
        raise NotImplementedError("ActionTerm.apply_actions must be overridden")

    def reset(self) -> None:
        self.raw_actions = [0.0] * self._dim
        self.processed_actions = [0.0] * self._dim


# ────────────────────────────────────────────────────────────────────────────
# JointEffortAction (torque control)
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class JointEffortActionCfg(ActionTermCfgBase):
    """Torque-control cfg. Action element = direct effort (Nm or N).

    Default `scale=1.0` means the raw action is the effort itself; for
    Cartpole-style "policy outputs in [-1, 1], scaled to force_mag" patterns
    set `scale=cartpole_cfg.force_mag` (typically 10.0).
    """


class JointEffortAction(ActionTerm):
    """Write processed action directly into env's effort buffer.

    Env contract: env exposes either `_applied_force` (single-DoF prismatic,
    Cartpole) or `_applied_torques` (multi-DoF revolute, DoublePendulum).
    The action term writes into whichever attribute exists, in joint_names
    order. If a joint index N is in `joint_names`, the term writes
    `processed_actions[i]` into `env._applied_torques[N]` (or
    `_applied_force` when N=0 and that attribute exists).
    """

    def apply_actions(self, env: Any) -> None:
        # Multi-DoF revolute path (DoublePendulum-like).
        if hasattr(env, "_applied_torques"):
            torques = list(env._applied_torques)
            # Extend if too short.
            while len(torques) < max(self.cfg.joint_names) + 1:
                torques.append(0.0)
            for slot, joint in enumerate(self.cfg.joint_names):
                if slot < len(self.processed_actions):
                    torques[joint] = self.processed_actions[slot]
            env._applied_torques = tuple(torques) if isinstance(env._applied_torques, tuple) else torques
            return
        # Single-DoF prismatic path (Cartpole-like).
        if hasattr(env, "_applied_force") and self.cfg.joint_names == [0]:
            env._applied_force = float(self.processed_actions[0])
            return
        # Fallback for envs that hold actions as `_actions[env_idx][joint]`
        # (DirectRLEnv subclasses). Write per-env-0 only here.
        if hasattr(env, "_actions") and env._actions:
            actions_per_env = env._actions[0]
            while len(actions_per_env) < max(self.cfg.joint_names) + 1:
                actions_per_env.append(0.0)
            for slot, joint in enumerate(self.cfg.joint_names):
                if slot < len(self.processed_actions):
                    actions_per_env[joint] = self.processed_actions[slot]
            return
        raise RuntimeError(
            f"JointEffortAction: env has no _applied_force / _applied_torques / "
            f"_actions buffer to write into"
        )


# ────────────────────────────────────────────────────────────────────────────
# JointPositionAction (PD position control)
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class JointPositionActionCfg(ActionTermCfgBase):
    """Position-target cfg with PD gains.

    Action element = target joint position. Effort = K_p * (target - q) -
    K_d * dq. `use_default_offset=True` (Isaac Lab default) treats raw=0 as
    "hold current default position" — useful for residual policies.
    """
    p_gain: float = 50.0
    d_gain: float = 5.0
    use_default_offset: bool = True


class JointPositionAction(ActionTerm):
    """PD controller — converts position target to torque via
    `tau = K_p (q_target - q) - K_d dq` and writes into env effort buffer."""

    cfg: JointPositionActionCfg

    def __init__(self, cfg: JointPositionActionCfg):
        super().__init__(cfg)
        # Per-joint default offset (current position at first apply or reset).
        self._default_q: List[float] = [0.0] * self._dim

    def reset(self) -> None:
        super().reset()
        self._default_q = [0.0] * self._dim

    def set_default_offset(self, env: Any) -> None:
        """Snapshot the current joint positions for the configured joints as
        the new default offset. Call at episode reset for residual policies."""
        if hasattr(env, "get_joint_positions"):
            q = env.get_joint_positions()
            for slot, joint in enumerate(self.cfg.joint_names):
                if 0 <= joint < len(q):
                    self._default_q[slot] = float(q[joint])

    def apply_actions(self, env: Any) -> None:
        cfg: JointPositionActionCfg = self.cfg  # type: ignore[assignment]
        # Read current joint state.
        if not (hasattr(env, "get_joint_positions") and hasattr(env, "get_joint_velocities")):
            raise RuntimeError(
                "JointPositionAction: env must expose get_joint_positions + get_joint_velocities"
            )
        q = env.get_joint_positions()
        dq = env.get_joint_velocities()
        # Compute torque per joint.
        torques_to_apply: List[tuple] = []  # (joint_idx, torque)
        for slot, joint in enumerate(self.cfg.joint_names):
            target = self.processed_actions[slot]
            if cfg.use_default_offset:
                target += self._default_q[slot]
            qj = q[joint] if joint < len(q) else 0.0
            dqj = dq[joint] if joint < len(dq) else 0.0
            tau = cfg.p_gain * (target - qj) - cfg.d_gain * dqj
            torques_to_apply.append((joint, tau))
        # Write into env effort buffer.
        if hasattr(env, "_applied_torques"):
            torques = list(env._applied_torques)
            max_idx = max((j for j, _ in torques_to_apply), default=0)
            while len(torques) < max_idx + 1:
                torques.append(0.0)
            for j, t in torques_to_apply:
                torques[j] = t
            env._applied_torques = tuple(torques) if isinstance(env._applied_torques, tuple) else torques
        elif hasattr(env, "_applied_force") and self.cfg.joint_names == [0]:
            env._applied_force = float(torques_to_apply[0][1])
        else:
            raise RuntimeError(
                "JointPositionAction: env has no _applied_force / _applied_torques buffer"
            )


# ────────────────────────────────────────────────────────────────────────────
# JointVelocityAction (P velocity control)
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class JointVelocityActionCfg(ActionTermCfgBase):
    """Velocity-target cfg. Effort = K_p * (target_vel - dq)."""
    p_gain: float = 10.0


class JointVelocityAction(ActionTerm):
    """P controller — converts velocity target to torque via
    `tau = K_p (dq_target - dq)`."""

    cfg: JointVelocityActionCfg

    def apply_actions(self, env: Any) -> None:
        cfg: JointVelocityActionCfg = self.cfg  # type: ignore[assignment]
        if not hasattr(env, "get_joint_velocities"):
            raise RuntimeError(
                "JointVelocityAction: env must expose get_joint_velocities"
            )
        dq = env.get_joint_velocities()
        torques_to_apply: List[tuple] = []
        for slot, joint in enumerate(self.cfg.joint_names):
            target_vel = self.processed_actions[slot]
            dqj = dq[joint] if joint < len(dq) else 0.0
            tau = cfg.p_gain * (target_vel - dqj)
            torques_to_apply.append((joint, tau))
        if hasattr(env, "_applied_torques"):
            torques = list(env._applied_torques)
            max_idx = max((j for j, _ in torques_to_apply), default=0)
            while len(torques) < max_idx + 1:
                torques.append(0.0)
            for j, t in torques_to_apply:
                torques[j] = t
            env._applied_torques = tuple(torques) if isinstance(env._applied_torques, tuple) else torques
        elif hasattr(env, "_applied_force") and self.cfg.joint_names == [0]:
            env._applied_force = float(torques_to_apply[0][1])
        else:
            raise RuntimeError(
                "JointVelocityAction: env has no _applied_force / _applied_torques buffer"
            )


# ────────────────────────────────────────────────────────────────────────────
# DifferentialInverseKinematicsAction (task-space pose → joint position target)
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class DifferentialInverseKinematicsActionCfg(ActionTermCfgBase):
    """Task-space inverse-kinematics action term cfg.

    Wraps `DifferentialIKController` (iter 41) — converts a task-space pose
    command (action vector) into joint-position deltas via damped least
    squares IK, then routes the resulting joint targets through a PD loop
    onto the env effort buffer.

    Action layout depends on `controller_cfg.command_type` ×
    `controller_cfg.use_relative_mode`:
      - `"pose"`     + abs: 7-vec (px, py, pz, qx, qy, qz, qw)
      - `"pose"`     + rel: 6-vec (dx, dy, dz, rx, ry, rz) axis-angle delta
      - `"position"` + abs/rel: 3-vec position only

    `body_name` is the EE link tracked by the env's Jacobian provider.
    `p_gain` / `d_gain` parametrise the PD loop that converts the
    IK-emitted joint targets into effort commands (same convention as
    `JointPositionActionCfg`).
    """
    body_name: str = "ee_link"
    controller_cfg: Optional[DifferentialIKControllerCfg] = None
    scale: float = 1.0
    offset: float = 0.0
    p_gain: float = 100.0
    d_gain: float = 10.0


class DifferentialInverseKinematicsAction(ActionTerm):
    """Compose `DifferentialIKController` behind the Isaac Lab ActionTerm
    interface.

    Pipeline:
      1. `process_actions(raw)` — scale+offset the raw task-space command,
         store as the IK controller's pending target.
      2. `apply_actions(env)` — read env Jacobian + EE pose + joint state,
         run IK to produce joint position targets, then PD into effort.

    Env contract (read):
      - `env.get_jacobian(body_name)` → 6×n list of lists
      - `env.get_ee_pose(body_name)`  → (pos_3, quat_4_xyzw) tuple
      - `env.get_joint_positions()`  → list[n_joints]
      - `env.get_joint_velocities()` → list[n_joints]
    Env contract (write):
      - same effort dispatch as `JointEffortAction` / `JointPositionAction`
        (`_applied_torques` / `_applied_force` / `_actions[0]` fallback).
    """

    cfg: DifferentialInverseKinematicsActionCfg

    def __init__(self, cfg: DifferentialInverseKinematicsActionCfg):
        # Build controller first so we can read its own action_dim.
        controller_cfg = cfg.controller_cfg or DifferentialIKControllerCfg()
        controller = DifferentialIKController(controller_cfg, num_envs=1)
        inferred = controller.action_dim  # 7 / 6 / 3 per cfg
        if cfg.action_dim is not None and cfg.action_dim != inferred:
            raise ValueError(
                f"DifferentialInverseKinematicsActionCfg: action_dim={cfg.action_dim} "
                f"contradicts controller action_dim={inferred}"
            )
        cfg.action_dim = inferred
        super().__init__(cfg)
        self._controller_cfg = controller_cfg
        self._ik = controller

    @property
    def controller(self) -> DifferentialIKController:
        return self._ik

    def reset(self) -> None:
        super().reset()
        self._ik.reset()

    def apply_actions(self, env: Any) -> None:
        cfg: DifferentialInverseKinematicsActionCfg = self.cfg  # type: ignore[assignment]
        # 1. Read env state.
        if not hasattr(env, "get_jacobian"):
            raise RuntimeError(
                "DifferentialInverseKinematicsAction: env must expose get_jacobian(body_name)"
            )
        if not hasattr(env, "get_ee_pose"):
            raise RuntimeError(
                "DifferentialInverseKinematicsAction: env must expose get_ee_pose(body_name)"
            )
        if not (hasattr(env, "get_joint_positions") and hasattr(env, "get_joint_velocities")):
            raise RuntimeError(
                "DifferentialInverseKinematicsAction: env must expose get_joint_positions + get_joint_velocities"
            )
        jacobian = env.get_jacobian(cfg.body_name)
        ee_pos, ee_quat = env.get_ee_pose(cfg.body_name)
        q_full = env.get_joint_positions()
        dq_full = env.get_joint_velocities()
        # Slice down to the joints this action controls.
        q_arm = [q_full[j] if j < len(q_full) else 0.0 for j in cfg.joint_names]
        dq_arm = [dq_full[j] if j < len(dq_full) else 0.0 for j in cfg.joint_names]
        # 2. Push processed command into the IK controller.
        self._ik.set_command(
            list(self.processed_actions), ee_pos=list(ee_pos), ee_quat=list(ee_quat),
        )
        # 3. Compute joint-space DELTA (not absolute target).
        joint_delta = self._ik.compute(
            ee_pos=list(ee_pos), ee_quat=list(ee_quat), jacobian=jacobian,
        )
        # 4. Joint target = q_arm + delta; PD into effort.
        torques_to_apply: List[tuple] = []
        for slot, joint in enumerate(cfg.joint_names):
            target = q_arm[slot] + joint_delta[slot]
            qj = q_full[joint] if joint < len(q_full) else 0.0
            dqj = dq_full[joint] if joint < len(dq_full) else 0.0
            tau = cfg.p_gain * (target - qj) - cfg.d_gain * dqj
            torques_to_apply.append((joint, tau))
        _write_effort(env, torques_to_apply, single_dof_force_ok=False)


# ────────────────────────────────────────────────────────────────────────────
# OperationalSpaceControllerAction (task-space torque control)
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class OperationalSpaceControllerActionCfg(ActionTermCfgBase):
    """Operational-space-control action term cfg.

    Wraps `OperationalSpaceController` (iter 63) — converts a task-space
    command (pose / wrench / variable impedance) directly into joint
    torques via Cartesian impedance + Jacobian transpose + (optional)
    null-space projection. Writes the resulting joint torques directly
    onto the env effort buffer — NO additional PD layer (the impedance
    loop IS the controller).

    Action layout matches `controller.action_dim` (varies with
    `target_types` and `impedance_mode`).

    `body_name` selects the EE link for the env's Jacobian/EE-pose
    providers. `nullspace_joint_targets` is optional (used only when
    `controller_cfg.nullspace_control != "none"`); if absent, the action
    falls back to the current joint positions (i.e. "stay where you are").

    `gravity_compensation_enabled` is mirrored from the controller cfg
    for convenience — when True, the env must expose `get_gravity_torque
    (body_name)` returning a per-joint gravity-torque vector.
    """
    body_name: str = "ee_link"
    controller_cfg: Optional[OperationalSpaceControllerCfg] = None
    nullspace_joint_targets: Optional[List[float]] = None
    scale: float = 1.0
    offset: float = 0.0


class OperationalSpaceControllerAction(ActionTerm):
    """Compose `OperationalSpaceController` behind the Isaac Lab ActionTerm
    interface. Action vector size matches `controller.action_dim`.

    Env contract (read):
      - `env.get_jacobian(body_name)` → 6×n list of lists
      - `env.get_ee_pose(body_name)`  → (pos_3, quat_4_xyzw)
      - `env.get_ee_velocity(body_name)` → (lin_vel_3, ang_vel_3)
      - `env.get_joint_positions()`  → list[n_joints]
      - `env.get_joint_velocities()` → list[n_joints]
      - (optional) `env.get_gravity_torque(body_name)` → list[n_joints]
        when `controller_cfg.gravity_compensation=True`.
    Env contract (write):
      - same effort dispatch as `JointEffortAction`.
    """

    cfg: OperationalSpaceControllerActionCfg

    def __init__(self, cfg: OperationalSpaceControllerActionCfg):
        controller_cfg = cfg.controller_cfg or OperationalSpaceControllerCfg()
        # Construct controller first to get action_dim.
        controller = OperationalSpaceController(
            controller_cfg, num_dof=len(cfg.joint_names),
        )
        inferred = controller.action_dim
        if cfg.action_dim is not None and cfg.action_dim != inferred:
            raise ValueError(
                f"OperationalSpaceControllerActionCfg: action_dim={cfg.action_dim} "
                f"contradicts controller action_dim={inferred}"
            )
        cfg.action_dim = inferred
        super().__init__(cfg)
        self._controller_cfg = controller_cfg
        self._osc = controller

    @property
    def controller(self) -> OperationalSpaceController:
        return self._osc

    def reset(self) -> None:
        super().reset()
        # OSC has no persistent step-state to clear beyond per-env target,
        # which is overwritten on every set_command.

    def apply_actions(self, env: Any) -> None:
        cfg: OperationalSpaceControllerActionCfg = self.cfg  # type: ignore[assignment]
        if not hasattr(env, "get_jacobian"):
            raise RuntimeError(
                "OperationalSpaceControllerAction: env must expose get_jacobian(body_name)"
            )
        if not hasattr(env, "get_ee_pose"):
            raise RuntimeError(
                "OperationalSpaceControllerAction: env must expose get_ee_pose(body_name)"
            )
        if not hasattr(env, "get_ee_velocity"):
            raise RuntimeError(
                "OperationalSpaceControllerAction: env must expose get_ee_velocity(body_name)"
            )
        if not (hasattr(env, "get_joint_positions") and hasattr(env, "get_joint_velocities")):
            raise RuntimeError(
                "OperationalSpaceControllerAction: env must expose get_joint_positions + get_joint_velocities"
            )
        jacobian = env.get_jacobian(cfg.body_name)
        ee_pos, ee_quat = env.get_ee_pose(cfg.body_name)
        ee_lin_vel, ee_ang_vel = env.get_ee_velocity(cfg.body_name)
        q_full = env.get_joint_positions()
        dq_full = env.get_joint_velocities()
        q_arm = [q_full[j] if j < len(q_full) else 0.0 for j in cfg.joint_names]
        dq_arm = [dq_full[j] if j < len(dq_full) else 0.0 for j in cfg.joint_names]

        # Pass action through to OSC. For pose_rel target_type the controller
        # needs the current EE pose; pass it through unconditionally (OSC
        # ignores when not in pose_rel mode).
        self._osc.set_command(
            list(self.processed_actions),
            ee_pos=list(ee_pos), ee_quat=list(ee_quat),
        )

        # Gravity compensation source.
        gravity_torque: Optional[List[float]] = None
        if getattr(self._controller_cfg, "gravity_compensation", False):
            if hasattr(env, "get_gravity_torque"):
                gravity_torque = list(env.get_gravity_torque(cfg.body_name))
            else:
                raise RuntimeError(
                    "OperationalSpaceControllerAction: gravity_compensation=True requires env.get_gravity_torque"
                )

        # Null-space target source.
        nullspace_target_pos: Optional[List[float]] = None
        if getattr(self._controller_cfg, "nullspace_control", "none") != "none":
            nullspace_target_pos = (
                list(cfg.nullspace_joint_targets)
                if cfg.nullspace_joint_targets is not None
                else list(q_arm)  # "stay where you are"
            )

        # Compute joint torques.
        compute_kwargs: Dict[str, Any] = dict(
            ee_pos=list(ee_pos), ee_quat=list(ee_quat),
            ee_lin_vel=list(ee_lin_vel), ee_ang_vel=list(ee_ang_vel),
            jacobian=jacobian,
            joint_pos=q_arm, joint_vel=dq_arm,
        )
        if nullspace_target_pos is not None:
            compute_kwargs["nullspace_target_pos"] = nullspace_target_pos
        if gravity_torque is not None:
            compute_kwargs["gravity_torque"] = gravity_torque
        joint_torques = self._osc.compute(**compute_kwargs)

        # Write directly to env effort buffer (no PD layer — OSC IS the loop).
        torques_to_apply: List[tuple] = [
            (joint, joint_torques[slot]) for slot, joint in enumerate(cfg.joint_names)
        ]
        _write_effort(env, torques_to_apply, single_dof_force_ok=False)


# ────────────────────────────────────────────────────────────────────────────
# BinaryJointAction (gripper open/close via single scalar action)
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class BinaryJointPositionActionCfg(ActionTermCfgBase):
    """Binary joint-position action — single scalar action drives a set
    of joints between two pre-configured pose-vectors (typically the
    "open" and "close" poses of a parallel-jaw gripper).

    Action layout:
      action_dim = 1
      action ∈ ℝ; mapped via `threshold`:
        action ≥ threshold → close_command (per-joint close pose)
        action <  threshold → open_command  (per-joint open pose)

    `open_command` / `close_command` must each be length `len(joint_names)`.
    `p_gain` / `d_gain` parametrise the PD loop that converts the
    selected pose into effort (mirrors JointPositionActionCfg).
    """
    open_command: List[float] = field(default_factory=list)
    close_command: List[float] = field(default_factory=list)
    threshold: float = 0.0
    p_gain: float = 100.0
    d_gain: float = 10.0


class BinaryJointPositionAction(ActionTerm):
    """Standard Isaac Lab gripper-style action term.

    Maps a scalar action to per-joint position targets via thresholding,
    then PDs into effort. Pairs naturally with iter 64
    DifferentialInverseKinematicsAction (arm) for arm + gripper task
    policies (`action = [pose_7..., gripper_1]`).

    `process_actions(raw)` retains scale + offset (inherited base
    behaviour) so policies that emit raw tanh in [-1, 1] can still
    map to the threshold; default cfg.scale=1.0 / offset=0.0 is fine
    for [-1, 1] policies with threshold=0.0.

    Env contract: same effort dispatch as JointPositionAction.
    """

    cfg: BinaryJointPositionActionCfg

    def __init__(self, cfg: BinaryJointPositionActionCfg):
        # Force action_dim=1 — binary gripper is one scalar regardless
        # of how many joints it drives.
        if cfg.action_dim is not None and cfg.action_dim != 1:
            raise ValueError(
                f"BinaryJointPositionActionCfg.action_dim must be 1 or None; got {cfg.action_dim}"
            )
        cfg.action_dim = 1
        super().__init__(cfg)
        n = len(cfg.joint_names)
        if len(cfg.open_command) != n:
            raise ValueError(
                f"BinaryJointPositionActionCfg.open_command length {len(cfg.open_command)} "
                f"must match joint_names length {n}"
            )
        if len(cfg.close_command) != n:
            raise ValueError(
                f"BinaryJointPositionActionCfg.close_command length {len(cfg.close_command)} "
                f"must match joint_names length {n}"
            )
        # Track which side was selected (False = open, True = close).
        self._is_close: bool = False

    @property
    def is_close(self) -> bool:
        return self._is_close

    def reset(self) -> None:
        super().reset()
        self._is_close = False

    def apply_actions(self, env: Any) -> None:
        cfg: BinaryJointPositionActionCfg = self.cfg  # type: ignore[assignment]
        if not (hasattr(env, "get_joint_positions") and hasattr(env, "get_joint_velocities")):
            raise RuntimeError(
                "BinaryJointPositionAction: env must expose get_joint_positions + get_joint_velocities"
            )
        # Single-scalar threshold dispatch.
        self._is_close = self.processed_actions[0] >= cfg.threshold
        target_pose = cfg.close_command if self._is_close else cfg.open_command
        q = env.get_joint_positions()
        dq = env.get_joint_velocities()
        torques_to_apply: List[tuple] = []
        for slot, joint in enumerate(cfg.joint_names):
            target = target_pose[slot]
            qj = q[joint] if joint < len(q) else 0.0
            dqj = dq[joint] if joint < len(dq) else 0.0
            tau = cfg.p_gain * (target - qj) - cfg.d_gain * dqj
            torques_to_apply.append((joint, tau))
        _write_effort(env, torques_to_apply, single_dof_force_ok=False)


# ────────────────────────────────────────────────────────────────────────────
# NonHolonomicAction (differential-drive mobile base — v_x + ω_z)
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class NonHolonomicActionCfg(ActionTermCfgBase):
    """Differential-drive non-holonomic action term cfg.

    Maps a 2-vector action (linear vel along chassis-x, angular vel
    around chassis-z) to per-wheel angular velocity targets via the
    standard differential-drive kinematics:
        ω_left  = (v − (ω · L / 2)) / r
        ω_right = (v + (ω · L / 2)) / r

    `joint_names` MUST be exactly 2 — [left_wheel_idx, right_wheel_idx].
    `wheel_radius` (r) and `wheel_separation` (L) in metres.
    `scale` / `offset` apply element-wise to the [v, ω] action; default
    scale=1.0 means the action elements are already in m/s and rad/s.

    `p_gain` parametrises the P-control loop that converts the wheel
    velocity targets into effort, mirroring JointVelocityActionCfg
    (no D term since target is velocity).
    """
    wheel_radius: float = 0.0
    wheel_separation: float = 0.0
    p_gain: float = 10.0


class NonHolonomicAction(ActionTerm):
    """Differential-drive controller — standard mobile-base action term.

    Action layout: [v_chassis_x (m/s), omega_chassis_z (rad/s)]
    action_dim = 2.

    Used together with iter 64 task-space actions for mobile
    manipulation (e.g. Spot, Stretch, Toyota HSR): `action = [v, ω,
    arm_pose_7..., gripper_1]` → ActionManager splits and dispatches.
    """

    cfg: NonHolonomicActionCfg

    def __init__(self, cfg: NonHolonomicActionCfg):
        if len(cfg.joint_names) != 2:
            raise ValueError(
                f"NonHolonomicActionCfg.joint_names must be [left_wheel, right_wheel] "
                f"(length 2); got length {len(cfg.joint_names)}"
            )
        if cfg.wheel_radius <= 0:
            raise ValueError(
                f"NonHolonomicActionCfg.wheel_radius must be > 0; got {cfg.wheel_radius}"
            )
        if cfg.wheel_separation <= 0:
            raise ValueError(
                f"NonHolonomicActionCfg.wheel_separation must be > 0; got {cfg.wheel_separation}"
            )
        if cfg.action_dim is not None and cfg.action_dim != 2:
            raise ValueError(
                f"NonHolonomicActionCfg.action_dim must be 2 or None; got {cfg.action_dim}"
            )
        cfg.action_dim = 2
        super().__init__(cfg)

    def process_actions(self, raw: List[float]) -> None:
        """Override to apply scale+offset element-wise (parent does
        the same already; explicit here to be safe across overrides)."""
        if len(raw) != 2:
            raise ValueError(
                f"NonHolonomicAction: expected 2 action elements (v_x, ω_z); got {len(raw)}"
            )
        self.raw_actions = list(raw)
        s, o = self.cfg.scale, self.cfg.offset
        self.processed_actions = [r * s + o for r in raw]

    def apply_actions(self, env: Any) -> None:
        cfg: NonHolonomicActionCfg = self.cfg  # type: ignore[assignment]
        if not hasattr(env, "get_joint_velocities"):
            raise RuntimeError(
                "NonHolonomicAction: env must expose get_joint_velocities"
            )
        v_x = self.processed_actions[0]
        omega_z = self.processed_actions[1]
        # Differential-drive inverse kinematics:
        # ω_wheel = (v ± ω·L/2) / r
        half_L = cfg.wheel_separation / 2.0
        omega_left = (v_x - omega_z * half_L) / cfg.wheel_radius
        omega_right = (v_x + omega_z * half_L) / cfg.wheel_radius
        # Store the wheel targets for telemetry / inspection.
        self._wheel_velocity_target = (omega_left, omega_right)
        # P-control onto effort (mirrors JointVelocityAction).
        dq = env.get_joint_velocities()
        left_joint, right_joint = cfg.joint_names
        dq_left = dq[left_joint] if left_joint < len(dq) else 0.0
        dq_right = dq[right_joint] if right_joint < len(dq) else 0.0
        tau_left = cfg.p_gain * (omega_left - dq_left)
        tau_right = cfg.p_gain * (omega_right - dq_right)
        _write_effort(
            env, [(left_joint, tau_left), (right_joint, tau_right)],
            single_dof_force_ok=False,
        )

    @property
    def wheel_velocity_target(self) -> tuple:
        """Most recently computed (ω_left, ω_right) wheel velocity targets."""
        return getattr(self, "_wheel_velocity_target", (0.0, 0.0))


# ────────────────────────────────────────────────────────────────────────────
# Shared effort-buffer write helper
# ────────────────────────────────────────────────────────────────────────────


def _write_effort(env: Any, torques_to_apply: List[tuple],
                   single_dof_force_ok: bool = True) -> None:
    """Write per-joint torques onto whichever effort buffer the env exposes.

    Mirrors the dispatch chain already used by `JointEffortAction` /
    `JointPositionAction` / `JointVelocityAction`:
      1. `env._applied_torques` (multi-DoF revolute)
      2. `env._applied_force` (single-DoF prismatic; only when only joint=0
         and `single_dof_force_ok=True`)
      3. `env._actions[0]` (DirectRLEnv per-env buffer)
    """
    if hasattr(env, "_applied_torques"):
        torques = list(env._applied_torques)
        max_idx = max((j for j, _ in torques_to_apply), default=0)
        while len(torques) < max_idx + 1:
            torques.append(0.0)
        for j, t in torques_to_apply:
            torques[j] = t
        env._applied_torques = (
            tuple(torques) if isinstance(env._applied_torques, tuple) else torques
        )
        return
    if (
        single_dof_force_ok
        and hasattr(env, "_applied_force")
        and len(torques_to_apply) == 1
        and torques_to_apply[0][0] == 0
    ):
        env._applied_force = float(torques_to_apply[0][1])
        return
    if hasattr(env, "_actions") and env._actions:
        actions_per_env = env._actions[0]
        max_idx = max((j for j, _ in torques_to_apply), default=0)
        while len(actions_per_env) < max_idx + 1:
            actions_per_env.append(0.0)
        for j, t in torques_to_apply:
            actions_per_env[j] = t
        return
    raise RuntimeError(
        "_write_effort: env has no _applied_torques / _applied_force / _actions buffer"
    )


# ────────────────────────────────────────────────────────────────────────────
# ActionManager — composes multiple terms
# ────────────────────────────────────────────────────────────────────────────


class ActionManager:
    """Composes multiple ActionTerm into a single combined action vector.

    `total_action_dim` = sum of each term's `action_dim`.
    `process_actions(raw)` slices `raw` by per-term offsets and dispatches
    each slice. `apply_actions(env)` then triggers every term's
    `apply_actions(env)` in registration order.

    Reset propagates to all terms (zeros internal buffers).
    """

    def __init__(self, terms: List[ActionTerm]):
        if not terms:
            raise ValueError("ActionManager requires at least one ActionTerm")
        self.terms: List[ActionTerm] = list(terms)
        self._term_names: List[str] = [type(t).__name__ for t in terms]
        # Cache per-term action slice offsets.
        self._offsets: List[int] = []
        off = 0
        for t in self.terms:
            self._offsets.append(off)
            off += t.action_dim
        self.total_action_dim: int = off

    def process_actions(self, raw: List[float]) -> None:
        """Slice `raw` and dispatch to each term in order."""
        if len(raw) != self.total_action_dim:
            raise ValueError(
                f"ActionManager: expected {self.total_action_dim} action elements, "
                f"got {len(raw)}"
            )
        for i, term in enumerate(self.terms):
            start = self._offsets[i]
            end = start + term.action_dim
            term.process_actions(raw[start:end])

    def apply_actions(self, env: Any) -> None:
        """Apply every term to env in registration order."""
        for term in self.terms:
            term.apply_actions(env)

    def reset(self, env_ids: Optional[List[int]] = None) -> None:
        """Reset all terms. `env_ids` is accepted for API parity but the
        nv_compat terms are env-agnostic (state is in the env)."""
        for term in self.terms:
            term.reset()

    @property
    def term_names(self) -> List[str]:
        return list(self._term_names)

    def num_terms(self) -> int:
        return len(self.terms)
