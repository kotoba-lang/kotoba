"""Standard termination functions — composable env-done conditions.

Mirror of `isaaclab.envs.mdp.terminations` (Isaac Lab 1.x). Each function
takes an env + optional params and returns a bool (True = terminate).
Wrap in iter 22 TerminationTerm and register with TerminationManager.

Surface (7 standard fns + 3 helpers):

  time_out(env, max_episode_steps=None)
      — episode length exceeded; the canonical "truncation" path
        (use time_out=True on the TerminationTerm so the manager flags
        it as truncation rather than hard termination).

  bad_orientation(env, limit_angle=1.5708)
      — robot base tilted past `limit_angle` rad (default π/2). Reads
        env.root_orientation (4-tuple) or env._state.theta (Cartpole)
        as orientation. Falls back to env._terminated when no source.

  root_height_below_minimum(env, minimum_height=0.0, asset_name="robot")
      — robot base z position below threshold (fell over). Reads
        env.root_position[2].

  joint_pos_out_of_limit(env, lower=None, upper=None, joint_indices=None)
      — any tracked joint position outside (lower, upper) range. Reads
        env.get_joint_positions().

  joint_vel_out_of_limit(env, limit=100.0, joint_indices=None)
      — any tracked joint velocity exceeds |limit|. Reads
        env.get_joint_velocities().

  illegal_contact(env, contact_sensor_name="", min_force=1.0)
      — contact sensor reports force > min_force on a disallowed link
        (e.g. robot base in contact with the ground = fell over). Reads
        env.contact_sensors[name].sample() — the iter 4 ContactSensor.

  base_contact(env, min_force=1.0)
      — alias of illegal_contact with contact_sensor_name="base"
        (most-common quadruped use case).

Each function is permissive: missing state → silent False (allows cfg
portability across envs that don't expose every sensor).

Pure stdlib (math).
"""

from __future__ import annotations

import math
from typing import Any, List, Optional


# ────────────────────────────────────────────────────────────────────────────
# Time-out
# ────────────────────────────────────────────────────────────────────────────


def time_out(env: Any, max_episode_steps: Optional[int] = None) -> bool:
    """True when episode length ≥ max_episode_steps.

    `max_episode_steps=None` reads from `env.max_episode_length` (iter 30
    DirectRLEnv convention) or `env._max_steps` (iter 14 manager-based).

    Use with `time_out=True` on the TerminationTerm to flag as truncation
    rather than hard termination — the manager separates these for
    bootstrapped value targets (gymnasium convention).
    """
    if max_episode_steps is None:
        max_episode_steps = (
            getattr(env, "max_episode_length", None)
            or getattr(env, "_max_steps", None)
            or 0
        )
    if max_episode_steps <= 0:
        return False
    # Vectorised step counter (DirectRLEnv) or scalar (ManagerBasedRLEnv).
    if hasattr(env, "episode_length_buf") and env.episode_length_buf:
        return env.episode_length_buf[0] >= max_episode_steps
    return int(getattr(env, "_steps", 0)) >= max_episode_steps


# ────────────────────────────────────────────────────────────────────────────
# Orientation + position checks
# ────────────────────────────────────────────────────────────────────────────


def bad_orientation(env: Any, limit_angle: float = math.pi / 2) -> bool:
    """True when robot base tilt exceeds `limit_angle` (radians).

    Reads orientation from (in order):
      1. env.root_orientation as quaternion (x, y, z, w); converts to
         tilt = acos(2(w² + z²) - 1)
      2. env._state.theta (Cartpole pole angle as a proxy)
    """
    quat = getattr(env, "root_orientation", None)
    if quat is not None and isinstance(quat, (tuple, list)) and len(quat) == 4:
        qx, qy, qz, qw = quat
        # Tilt from +z = acos(z·z_world) where z_world axis after rotation
        # is (2(xz + wy), 2(yz - wx), 1 - 2(x² + y²)). Tilt vs world +z:
        cos_tilt = max(-1.0, min(1.0, 1.0 - 2.0 * (qx * qx + qy * qy)))
        tilt = math.acos(cos_tilt)
        return tilt >= limit_angle
    # Cartpole fallback — use pole angle as proxy for tilt.
    state = getattr(env, "_state", None)
    if state is not None and hasattr(state, "theta"):
        return abs(state.theta) >= limit_angle
    return False


def root_height_below_minimum(
    env: Any,
    minimum_height: float = 0.0,
    asset_name: str = "robot",
) -> bool:
    """True when robot base z position is below `minimum_height`.

    Reads env.root_position (3-tuple). Common values: 0.3m for ANYmal,
    0.4m for unitree humanoid (anything below = fell over).
    """
    pos = getattr(env, "root_position", None)
    if pos is None or not isinstance(pos, (tuple, list)) or len(pos) < 3:
        return False
    return pos[2] < minimum_height


# ────────────────────────────────────────────────────────────────────────────
# Joint limits
# ────────────────────────────────────────────────────────────────────────────


def joint_pos_out_of_limit(
    env: Any,
    lower: Optional[float] = None,
    upper: Optional[float] = None,
    joint_indices: Optional[List[int]] = None,
) -> bool:
    """True when any tracked joint position is outside (lower, upper).

    `joint_indices=None` checks every joint. `lower=None` means -∞;
    `upper=None` means +∞ (use both None as a no-op).
    """
    if not hasattr(env, "get_joint_positions"):
        return False
    q = env.get_joint_positions()
    indices = joint_indices if joint_indices is not None else range(len(q))
    for i in indices:
        if i >= len(q):
            continue
        if lower is not None and q[i] < lower:
            return True
        if upper is not None and q[i] > upper:
            return True
    return False


def joint_vel_out_of_limit(
    env: Any,
    limit: float = 100.0,
    joint_indices: Optional[List[int]] = None,
) -> bool:
    """True when any tracked joint velocity magnitude exceeds `limit`."""
    if not hasattr(env, "get_joint_velocities"):
        return False
    dq = env.get_joint_velocities()
    indices = joint_indices if joint_indices is not None else range(len(dq))
    return any(
        abs(dq[i]) > limit for i in indices if i < len(dq)
    )


# ────────────────────────────────────────────────────────────────────────────
# Contact-based termination
# ────────────────────────────────────────────────────────────────────────────


def illegal_contact(
    env: Any,
    contact_sensor_name: str = "",
    min_force: float = 1.0,
) -> bool:
    """True when a named ContactSensor (iter 4) reports contact_force
    above `min_force`. Used to detect 'fell over' (base touched ground)
    or 'illegal limb contact' (knee touched ground).

    Reads `env.contact_sensors[name]` (typical iter 27 InteractiveScene
    sensor mount). Falls back to `env._latest_observations[0][name]` for
    iter 28 scene auto-sample integration.

    Returns False when no sensor by that name is registered.
    """
    if not contact_sensor_name:
        return False
    # Direct sensor reading.
    sensors = getattr(env, "contact_sensors", None)
    reading = None
    if isinstance(sensors, dict) and contact_sensor_name in sensors:
        sensor = sensors[contact_sensor_name]
        if hasattr(sensor, "_last_reading"):
            reading = sensor._last_reading
    # Iter 28 InteractiveScene auto-sample cache.
    if reading is None:
        scene = getattr(env, "scene", None)
        if scene is not None and hasattr(scene, "get_latest_observation"):
            reading = scene.get_latest_observation(0, contact_sensor_name)
    if reading is None:
        return False
    # ContactReading.in_contact is the bool we want; threshold via
    # penetration_depth or contact_force when available.
    if hasattr(reading, "in_contact") and reading.in_contact:
        # Convert penetration to "force" proxy (deeper = harder contact).
        depth = getattr(reading, "penetration_depth", 0.0)
        return depth >= min_force / 100.0  # rough scale to map N → m
    return False


def base_contact(env: Any, min_force: float = 1.0) -> bool:
    """Alias: `illegal_contact(env, "base", min_force)` — most common
    quadruped failure detector (robot base touched the ground)."""
    return illegal_contact(env, contact_sensor_name="base", min_force=min_force)


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def any_of(*conditions: Any) -> bool:
    """True when any supplied bool / callable evaluates True. Useful for
    composing custom multi-condition termination terms without a full
    TerminationTerm chain:

        TerminationTerm(func=lambda env: any_of(
            bad_orientation(env), root_height_below_minimum(env, 0.3),
        ), time_out=False)
    """
    for c in conditions:
        if callable(c):
            if c():
                return True
        elif c:
            return True
    return False


def all_of(*conditions: Any) -> bool:
    """Conjunction of conditions (AND). Counterpart to any_of."""
    for c in conditions:
        if callable(c):
            if not c():
                return False
        elif not c:
            return False
    return True


def negate(condition: Any) -> bool:
    """NOT — handy for nesting in any_of / all_of expressions."""
    if callable(condition):
        return not condition()
    return not bool(condition)
