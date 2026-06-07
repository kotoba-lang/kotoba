"""Event terms — reset / mid-episode events.

Each mdp event function takes the env + optional params and may mutate the
env state (e.g. reset joint positions, randomise physics). Returns None.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class EventTerm:
    """One event term in a manager-based env config.

    `mode` follows Isaac Lab convention:
      - "reset"    — fires on episode reset
      - "interval" — fires every N steps within an episode
      - "startup"  — fires once at env construction
    """
    func: Callable
    mode: str = "reset"
    interval_steps: int = 0  # only used when mode == "interval"
    params: dict = field(default_factory=dict)

    def evaluate(self, env) -> None:
        self.func(env, **self.params)


# Seedable LCG matching nv_compat conventions.
class _Lcg:
    def __init__(self, seed: int):
        self.state = (seed * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF

    def next_u01(self) -> float:
        self.state = (self.state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return ((self.state >> 33) & 0x7FFFFFFF) / float(1 << 31)


# ── Standard event functions ──────────────────────────────────────────────

def reset_joints_by_offset(env, position_range: tuple = (-0.1, 0.1),
                           velocity_range: tuple = (-0.1, 0.1),
                           seed: Optional[int] = None,
                           asset_cfg: Optional[str] = None) -> None:
    """Reset joints to default + uniform offset in (low, high)."""
    rng = _Lcg(seed if seed is not None else 0)
    pos = list(env.get_joint_positions())
    vel = list(env.get_joint_velocities())
    for i in range(len(pos)):
        pos[i] = position_range[0] + (position_range[1] - position_range[0]) * rng.next_u01()
    for i in range(len(vel)):
        vel[i] = velocity_range[0] + (velocity_range[1] - velocity_range[0]) * rng.next_u01()
    env.set_joint_positions(pos)
    env.set_joint_velocities(vel)


def reset_joints_to_default(env, asset_cfg: Optional[str] = None) -> None:
    """Reset joints to zero (or env-defined default)."""
    defaults = getattr(env, "_default_joint_pos", None)
    n_pos = len(env.get_joint_positions())
    pos = defaults if defaults is not None else [0.0] * n_pos
    env.set_joint_positions(list(pos))
    env.set_joint_velocities([0.0] * n_pos)


def randomize_rigid_body_mass(env, mass_range: tuple = (0.8, 1.2),
                              seed: Optional[int] = None,
                              asset_cfg: Optional[str] = None,
                              body_name: Optional[str] = None) -> None:
    """Randomise a rigid body's mass within mass_range. For Cartpole this
    affects cart_mass; for DP it affects link1 mass. Defaults to cart_mass.

    The env must expose `_cartpole_cfg.cart_mass` and `_dp_cfg.{m1, m2}` for
    this to land (matches the existing ManagerBasedRLEnv state layout).
    """
    rng = _Lcg(seed if seed is not None else 0)
    new_mass = mass_range[0] + (mass_range[1] - mass_range[0]) * rng.next_u01()
    cfg = getattr(env, "_cartpole_cfg", None)
    if cfg is not None:
        # CartpoleConfig is mutable dataclass.
        cfg.cart_mass = new_mass
        return
    dp_cfg = getattr(env, "_dp_cfg", None)
    if dp_cfg is not None:
        dp_cfg.m1 = new_mass


# ── Domain-randomization event extensions (iter 62) ────────────────────────


from typing import List as _List


def _uniform(rng: _Lcg, range_t: tuple) -> float:
    return range_t[0] + (range_t[1] - range_t[0]) * rng.next_u01()


def push_by_setting_velocity(
    env,
    velocity_range: tuple = (-1.0, 1.0),
    angular_velocity_range: tuple = (-1.0, 1.0),
    push_axis: tuple = (1.0, 1.0, 0.0),
    angular_axis: tuple = (0.0, 0.0, 1.0),
    seed: Optional[int] = None,
    asset_cfg: Optional[str] = None,
) -> None:
    """Sim2real robustness perturbation — push the base by setting a
    sudden velocity in (push_axis weighted by uniform sample).

    Standard quadruped event: every N seconds the simulator applies a
    random impulse to test recovery. Reads/writes env.root_linear_velocity
    and env.root_angular_velocity (iter 43 Articulation accessor).

    Permissive: when env exposes neither, the function is a silent no-op.
    """
    rng = _Lcg(seed if seed is not None else 0)
    # Linear push: pick magnitude in velocity_range, project onto push_axis.
    push_mag = _uniform(rng, velocity_range)
    delta_v = (
        push_mag * push_axis[0],
        push_mag * push_axis[1],
        push_mag * push_axis[2],
    )
    if hasattr(env, "root_linear_velocity"):
        v = env.root_linear_velocity
        env.root_linear_velocity = (
            v[0] + delta_v[0], v[1] + delta_v[1], v[2] + delta_v[2],
        )
    elif hasattr(env, "_base_lin_vel"):
        env._base_lin_vel = delta_v

    # Angular push.
    ang_mag = _uniform(rng, angular_velocity_range)
    delta_w = (
        ang_mag * angular_axis[0],
        ang_mag * angular_axis[1],
        ang_mag * angular_axis[2],
    )
    if hasattr(env, "root_angular_velocity"):
        w = env.root_angular_velocity
        env.root_angular_velocity = (
            w[0] + delta_w[0], w[1] + delta_w[1], w[2] + delta_w[2],
        )
    elif hasattr(env, "_base_ang_vel"):
        env._base_ang_vel = delta_w


def randomize_actuator_gains(
    env,
    p_gain_range: tuple = (0.8, 1.2),
    d_gain_range: tuple = (0.8, 1.2),
    seed: Optional[int] = None,
    actuator_name: Optional[str] = None,
    multiplicative: bool = True,
    asset_cfg: Optional[str] = None,
) -> None:
    """Randomize per-env PD gains within (p_gain_range, d_gain_range).

    When `multiplicative=True` (default), ranges are multipliers on the
    actuator's nominal stiffness/damping (e.g. 0.8-1.2 → ±20% perturbation).
    When `multiplicative=False`, ranges are absolute K_p / K_d values.

    Reads `env.actuators` dict (iter 45 actuator group registry); when
    `actuator_name` is None, randomizes every actuator in the dict.
    Permissive — no-op when env has no actuators.
    """
    rng = _Lcg(seed if seed is not None else 0)
    actuators = getattr(env, "actuators", None)
    if not isinstance(actuators, dict):
        return
    targets = (
        [actuator_name] if actuator_name and actuator_name in actuators
        else list(actuators.keys())
    )
    for name in targets:
        actuator = actuators[name]
        p_factor = _uniform(rng, p_gain_range)
        d_factor = _uniform(rng, d_gain_range)
        if multiplicative:
            actuator.stiffness = [s * p_factor for s in actuator.stiffness]
            actuator.damping = [d * d_factor for d in actuator.damping]
        else:
            actuator.stiffness = [p_factor] * len(actuator.stiffness)
            actuator.damping = [d_factor] * len(actuator.damping)


def apply_external_force_torque(
    env,
    force_range: tuple = (0.0, 0.0),
    torque_range: tuple = (0.0, 0.0),
    direction: tuple = (0.0, 0.0, 0.0),
    seed: Optional[int] = None,
    asset_cfg: Optional[str] = None,
    body_name: str = "base",
) -> None:
    """Apply a constant external force + torque on the named body.

    Standard "wind" perturbation — applied every step (mode="interval")
    to test policy robustness under push disturbance. Writes to
    `env._external_forces[body_name]` and `env._external_torques[body_name]`
    dicts that the host physics step reads at integration time.

    When `direction != (0,0,0)`, the random magnitude is projected onto
    `direction`. Otherwise the force is sampled uniformly in each axis.
    """
    rng = _Lcg(seed if seed is not None else 0)
    if direction != (0.0, 0.0, 0.0):
        mag = _uniform(rng, force_range)
        d = direction
        # Normalize.
        n = math.sqrt(d[0]**2 + d[1]**2 + d[2]**2) or 1.0
        force = (mag * d[0] / n, mag * d[1] / n, mag * d[2] / n)
        tmag = _uniform(rng, torque_range)
        torque = (tmag * d[0] / n, tmag * d[1] / n, tmag * d[2] / n)
    else:
        force = tuple(_uniform(rng, force_range) for _ in range(3))
        torque = tuple(_uniform(rng, torque_range) for _ in range(3))

    if not hasattr(env, "_external_forces"):
        env._external_forces = {}
    if not hasattr(env, "_external_torques"):
        env._external_torques = {}
    env._external_forces[body_name] = force
    env._external_torques[body_name] = torque


def randomize_friction(
    env,
    friction_range: tuple = (0.5, 1.5),
    seed: Optional[int] = None,
    asset_cfg: Optional[str] = None,
    body_names: Optional[_List[str]] = None,
) -> None:
    """Randomize surface friction coefficients per env.

    Writes `env._friction[body_name] = (static, dynamic)` dict. When
    `body_names=None`, applies a single per-env friction (same value to
    all bodies). Otherwise applies per-body sampled values.

    Static and dynamic friction sampled identically within friction_range;
    dynamic = static is a common simplification matching Isaac Sim default.
    """
    rng = _Lcg(seed if seed is not None else 0)
    if not hasattr(env, "_friction"):
        env._friction = {}
    targets = body_names if body_names else ["base"]
    for body in targets:
        mu = _uniform(rng, friction_range)
        env._friction[body] = (mu, mu)


def randomize_com(
    env,
    com_range_xyz: tuple = ((-0.05, 0.05), (-0.05, 0.05), (-0.05, 0.05)),
    seed: Optional[int] = None,
    asset_cfg: Optional[str] = None,
    body_name: str = "base",
) -> None:
    """Randomize center-of-mass offset per env.

    Writes env._com_offset[body_name] = (x, y, z) per env. Each axis
    sampled independently from com_range_xyz[axis] = (lo, hi).

    Subtle sim2real DR — small CoM shifts (±5cm) within the body to
    mimic battery placement / cable routing variation in the real robot.
    """
    rng = _Lcg(seed if seed is not None else 0)
    if not hasattr(env, "_com_offset"):
        env._com_offset = {}
    env._com_offset[body_name] = (
        _uniform(rng, com_range_xyz[0]),
        _uniform(rng, com_range_xyz[1]),
        _uniform(rng, com_range_xyz[2]),
    )


def randomize_mass(
    env,
    mass_range: tuple = (0.8, 1.2),
    seed: Optional[int] = None,
    multiplicative: bool = True,
    asset_cfg: Optional[str] = None,
    body_name: str = "base",
) -> None:
    """Generalised mass randomization (supports multiplicative perturbation
    on nominal mass vs absolute mass setting).

    Cleaner version of iter 22 randomize_rigid_body_mass that doesn't
    couple to the kernel's _cartpole_cfg.cart_mass attribute. Writes
    env._body_masses[body_name] = mass which the host reads when building
    per-env physics configs.
    """
    rng = _Lcg(seed if seed is not None else 0)
    if not hasattr(env, "_body_masses"):
        env._body_masses = {}
    if multiplicative:
        # Read nominal mass; default to 1.0 when unavailable.
        nominal = env._body_masses.get(body_name, 1.0)
        factor = _uniform(rng, mass_range)
        env._body_masses[body_name] = nominal * factor
    else:
        env._body_masses[body_name] = _uniform(rng, mass_range)


def randomize_initial_root_pose(
    env,
    pos_x_range: tuple = (-0.5, 0.5),
    pos_y_range: tuple = (-0.5, 0.5),
    pos_z_range: tuple = (0.0, 0.0),
    yaw_range: tuple = (-3.14159, 3.14159),
    seed: Optional[int] = None,
    asset_cfg: Optional[str] = None,
) -> None:
    """Randomize initial root pose (x, y, z, yaw) at episode reset.

    Pitch + roll fixed to 0 (typical legged-locomotion reset — robot
    starts upright). Yaw uniformly in yaw_range so the policy learns
    rotational invariance.

    Mutates env.root_position + env.root_orientation directly.
    """
    rng = _Lcg(seed if seed is not None else 0)
    pos = (
        _uniform(rng, pos_x_range),
        _uniform(rng, pos_y_range),
        _uniform(rng, pos_z_range),
    )
    yaw = _uniform(rng, yaw_range)
    half_yaw = yaw * 0.5
    quat = (0.0, 0.0, math.sin(half_yaw), math.cos(half_yaw))
    if hasattr(env, "root_position"):
        env.root_position = pos
    if hasattr(env, "root_orientation"):
        env.root_orientation = quat
    # Asset-style write_root_pose accessor (iter 43 Articulation).
    if hasattr(env, "write_root_pose"):
        env.write_root_pose(pos, quat)
