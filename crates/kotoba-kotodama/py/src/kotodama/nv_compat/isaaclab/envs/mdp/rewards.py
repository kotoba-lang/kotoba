"""Reward terms — composable reward function builders.

Each mdp reward function takes an env + optional params and returns a scalar.
RewGroup composes multiple weighted RewTerm into the final scalar reward.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class RewTerm:
    """One reward term in a manager-based env config.

    Final contribution = weight * func(env, **params).
    """
    func: Callable
    weight: float = 1.0
    params: dict = field(default_factory=dict)

    def evaluate(self, env) -> float:
        return self.weight * float(self.func(env, **self.params))


@dataclass
class RewGroup:
    """Composes multiple RewTerm into a scalar reward (sum of weighted terms)."""
    terms: dict = field(default_factory=dict)

    def evaluate(self, env) -> float:
        return sum(term.evaluate(env) for term in self.terms.values())

    def evaluate_breakdown(self, env) -> dict:
        """Per-term contributions (debug)."""
        return {name: term.evaluate(env) for name, term in self.terms.items()}

    def add(self, name: str, term: RewTerm) -> "RewGroup":
        self.terms[name] = term
        return self


# ── Standard reward functions ─────────────────────────────────────────────

def is_alive(env, asset_cfg: Optional[str] = None) -> float:
    """1.0 if the env is not in a terminated state."""
    return 0.0 if getattr(env, "_terminated", False) else 1.0


def is_terminated(env, asset_cfg: Optional[str] = None) -> float:
    """1.0 if env is in a terminated state (use with negative weight)."""
    return 1.0 if getattr(env, "_terminated", False) else 0.0


def joint_pos_l2(env, asset_cfg: Optional[str] = None,
                 joint_names: Optional[list] = None) -> float:
    """Sum of squared joint positions (penalises deviation from zero).

    If `joint_names` is given, only those joints (by index in the env's
    joint list) contribute. For Cartpole conventionally [1] = pole.
    """
    pos = env.get_joint_positions()
    if joint_names is None:
        return sum(p * p for p in pos)
    return sum(pos[i] * pos[i] for i in joint_names if i < len(pos))


def joint_vel_l2(env, asset_cfg: Optional[str] = None,
                 joint_names: Optional[list] = None) -> float:
    """Sum of squared joint velocities."""
    vel = env.get_joint_velocities()
    if joint_names is None:
        return sum(v * v for v in vel)
    return sum(vel[i] * vel[i] for i in joint_names if i < len(vel))


def action_l2(env, asset_cfg: Optional[str] = None) -> float:
    """L2 of last action (penalises large control effort)."""
    a = getattr(env, "_last_action", []) or []
    return sum(x * x for x in a)


def action_rate_l2(env, asset_cfg: Optional[str] = None) -> float:
    """L2 of action delta from previous step (penalises jerky control)."""
    a = getattr(env, "_last_action", []) or []
    prev = getattr(env, "_prev_action", []) or [0.0] * len(a)
    return sum((a[i] - prev[i]) ** 2 for i in range(min(len(a), len(prev))))


def joint_torques_l2(env, asset_cfg: Optional[str] = None) -> float:
    """L2 of last torques applied (mirrors action_l2 when there's no
    separate controller path; falls back to action_l2 when torques are
    not exposed)."""
    torques = getattr(env, "_last_torques", None)
    if torques is None:
        return action_l2(env, asset_cfg)
    return sum(t * t for t in torques)


# ── Locomotion reward extensions (iter 60) ────────────────────────────────


import math as _math
from typing import List


def _read_command(env, command_name: str, expected_len: int) -> Optional[list]:
    """Helper — pull a command vector by name from `env._commands` dict.
    Returns None when the env has no commands wired or the named command
    has the wrong length."""
    cmds = getattr(env, "_commands", None)
    if cmds is None or command_name not in cmds:
        return None
    cmd = cmds[command_name]
    # Multi-env layout: list-of-per-env. Use env 0 by default.
    if cmd and isinstance(cmd[0], (list, tuple)):
        cmd = cmd[0]
    if len(cmd) < expected_len:
        return None
    return cmd


def _read_base_lin_vel(env) -> tuple:
    """Read base linear velocity (3-tuple). Sources tried in order:
      1. env.root_linear_velocity (iter 43 Articulation accessor)
      2. env.base_lin_vel / env._base_lin_vel
      3. fallback to (joint_vel[0], 0, 0) — Cartpole cart proxy
    """
    v = getattr(env, "root_linear_velocity", None)
    if v is not None and len(v) >= 3:
        return (v[0], v[1], v[2])
    v = getattr(env, "_base_lin_vel", None) or getattr(env, "base_lin_vel", None)
    if v is not None and len(v) >= 3:
        return (v[0], v[1], v[2])
    if hasattr(env, "get_joint_velocities"):
        dq = env.get_joint_velocities()
        return (dq[0] if dq else 0.0, 0.0, 0.0)
    return (0.0, 0.0, 0.0)


def _read_base_ang_vel(env) -> tuple:
    """Read base angular velocity (3-tuple). Similar fallback chain to
    _read_base_lin_vel."""
    v = getattr(env, "root_angular_velocity", None)
    if v is not None and len(v) >= 3:
        return (v[0], v[1], v[2])
    v = getattr(env, "_base_ang_vel", None) or getattr(env, "base_ang_vel", None)
    if v is not None and len(v) >= 3:
        return (v[0], v[1], v[2])
    return (0.0, 0.0, 0.0)


def _read_root_quat(env) -> tuple:
    """Read base orientation quaternion (x, y, z, w). Returns identity
    when no source available."""
    q = getattr(env, "root_orientation", None)
    if q is not None and len(q) == 4:
        return (q[0], q[1], q[2], q[3])
    return (0.0, 0.0, 0.0, 1.0)


def _projected_gravity(quat: tuple, gravity: tuple = (0.0, 0.0, -1.0)) -> tuple:
    """Rotate world-frame gravity into body frame via quat^-1 · g · quat.
    Used for flat_orientation_l2 (flat = body z aligned with world z =
    projected gravity in body frame ≈ (0, 0, -1))."""
    qx, qy, qz, qw = quat
    gx, gy, gz = gravity
    # Conjugate quaternion rotation: v_body = q^-1 v_world q
    # Using formula v' = v + 2 * cross(q.xyz, cross(q.xyz, v) + q.w * v)
    # For inverse rotation, negate the xyz part.
    qx, qy, qz = -qx, -qy, -qz
    cx = qy * gz - qz * gy
    cy = qz * gx - qx * gz
    cz = qx * gy - qy * gx
    cx += qw * gx
    cy += qw * gy
    cz += qw * gz
    rx = gx + 2.0 * (qy * cz - qz * cy)
    ry = gy + 2.0 * (qz * cx - qx * cz)
    rz = gz + 2.0 * (qx * cy - qy * cx)
    return (rx, ry, rz)


def track_lin_vel_xy_exp(
    env,
    command_name: str = "velocity",
    std: float = 0.5,
    asset_cfg: Optional[str] = None,
) -> float:
    """Track commanded base linear velocity (x, y) — exponential reward.

    reward = exp(-‖v_cmd_xy - v_actual_xy‖² / std²)

    Reads command from env._commands[command_name] (iter 39 UniformVelocity
    command emits [vx, vy, vz, wz] — uses first 2). Returns 0 when no
    command is wired (cfg portability).
    """
    cmd = _read_command(env, command_name, 2)
    if cmd is None:
        return 0.0
    actual = _read_base_lin_vel(env)
    err_sq = (cmd[0] - actual[0]) ** 2 + (cmd[1] - actual[1]) ** 2
    return _math.exp(-err_sq / (std * std + 1e-12))


def track_ang_vel_z_exp(
    env,
    command_name: str = "velocity",
    std: float = 0.5,
    asset_cfg: Optional[str] = None,
) -> float:
    """Track commanded base angular velocity (yaw rate) — exponential reward.

    reward = exp(-(w_cmd_z - w_actual_z)² / std²)

    Reads command[3] (wz) from env._commands[command_name].
    """
    cmd = _read_command(env, command_name, 4)
    if cmd is None:
        return 0.0
    actual = _read_base_ang_vel(env)
    err = cmd[3] - actual[2]  # cmd[3]=wz, actual[2]=ω_z
    return _math.exp(-(err * err) / (std * std + 1e-12))


def flat_orientation_l2(env, asset_cfg: Optional[str] = None) -> float:
    """Penalise tilt — L2 of projected-gravity xy components.

    Flat upright robot → projected gravity in body frame = (0, 0, -1) →
    xy² = 0. Tilted → xy² > 0. Use with NEGATIVE weight.
    """
    pg = _projected_gravity(_read_root_quat(env))
    return pg[0] * pg[0] + pg[1] * pg[1]


def lin_vel_z_l2(env, asset_cfg: Optional[str] = None) -> float:
    """Penalise vertical base velocity (jumping / bouncing). Use with
    negative weight."""
    v = _read_base_lin_vel(env)
    return v[2] * v[2]


def ang_vel_xy_l2(env, asset_cfg: Optional[str] = None) -> float:
    """Penalise non-yaw angular velocity (roll + pitch rates). Use with
    negative weight."""
    w = _read_base_ang_vel(env)
    return w[0] * w[0] + w[1] * w[1]


def feet_air_time(
    env,
    sensor_names: Optional[List[str]] = None,
    threshold: float = 0.5,
    command_name: str = "velocity",
    command_threshold: float = 0.1,
) -> float:
    """Sum of (foot air time - threshold) over feet at first contact.

    Standard quadruped reward — rewards each foot for being airborne
    near `threshold` seconds (encourages a natural gait rhythm vs
    constant-contact shuffle).

    Implementation: tracks per-foot air-time accumulator in
    `env._foot_air_time` dict, indexed by sensor_name. Host increments
    by physics_dt each step; this function reads + resets on contact
    transition (first contact since liftoff).

    `command_threshold` zeros the reward when commanded vel is very low
    (don't reward gait when standing still). Returns 0 when no sensors
    wired (cfg portability).
    """
    if not sensor_names:
        return 0.0
    # Zero reward when no command or command magnitude tiny.
    cmd = _read_command(env, command_name, 4)
    if cmd is not None:
        cmd_mag = _math.sqrt(cmd[0] ** 2 + cmd[1] ** 2 + cmd[3] ** 2)
        if cmd_mag < command_threshold:
            return 0.0
    # Pull per-foot air time + contact state.
    air_times = getattr(env, "_foot_air_time", None)
    contacts = getattr(env, "_foot_in_contact", None)
    last_contacts = getattr(env, "_foot_prev_contact", None)
    if air_times is None or contacts is None:
        return 0.0
    total = 0.0
    for name in sensor_names:
        if name not in contacts or name not in air_times:
            continue
        in_contact = contacts[name]
        was_in_contact = last_contacts.get(name, False) if last_contacts else False
        if in_contact and not was_in_contact:
            # First contact: reward the airborne duration (truncated by threshold).
            total += min(air_times[name], threshold)
            air_times[name] = 0.0
    return total


def dof_pos_limits(
    env,
    soft_ratio: float = 1.0,
    asset_cfg: Optional[str] = None,
) -> float:
    """Penalise joint positions near soft limits.

    Reads env.cfg.joint_pos_limits = list of (lower, upper) per joint,
    OR falls back to (-π, π) for every joint. Computes L2 of the
    out-of-limit excess (clipped at zero — only penalise when past
    soft_ratio * limit). Use with negative weight.
    """
    if not hasattr(env, "get_joint_positions"):
        return 0.0
    q = env.get_joint_positions()
    cfg = getattr(env, "cfg", None)
    limits = getattr(cfg, "joint_pos_limits", None) if cfg else None
    total = 0.0
    for i, qi in enumerate(q):
        if limits and i < len(limits):
            lo, hi = limits[i]
        else:
            lo, hi = -_math.pi, _math.pi
        soft_lo = soft_ratio * lo
        soft_hi = soft_ratio * hi
        excess = max(0.0, soft_lo - qi) + max(0.0, qi - soft_hi)
        total += excess * excess
    return total


def dof_torques_l2(env, asset_cfg: Optional[str] = None) -> float:
    """L2 of applied joint torques. Alias of `joint_torques_l2` but with
    the canonical Isaac Lab name (matches anymal_c reference cfg)."""
    return joint_torques_l2(env, asset_cfg)


def alive_bonus(env, bonus: float = 1.0,
                 asset_cfg: Optional[str] = None) -> float:
    """Constant bonus while alive. Identical to `is_alive` × bonus —
    provided for cfg readability."""
    return bonus * is_alive(env, asset_cfg)
