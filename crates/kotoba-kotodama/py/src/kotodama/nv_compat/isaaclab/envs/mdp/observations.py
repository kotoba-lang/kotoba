"""Observation terms — composable observation builders.

Each mdp observation function takes an env (with get_joint_positions /
get_joint_velocities accessors) and returns a list of floats. Functions
support an optional `asset_cfg` parameter naming a specific articulation,
matching the Isaac Lab pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ObsTerm:
    """One observation term in a manager-based env config.

    `func` is called as `func(env, **params)` and must return a list[float]
    (or a single float). `scale` multiplies the raw output; `clip` caps to
    (low, high) magnitude.
    """
    func: Callable
    params: dict = field(default_factory=dict)
    scale: float = 1.0
    clip: Optional[tuple] = None  # (low, high) or None

    def evaluate(self, env) -> list:
        raw = self.func(env, **self.params)
        if not isinstance(raw, list):
            raw = [raw]
        out = [x * self.scale for x in raw]
        if self.clip is not None:
            low, high = self.clip
            out = [max(low, min(high, v)) for v in out]
        return out


@dataclass
class ObsGroup:
    """Composes multiple ObsTerm into a single observation vector.

    Iteration order is insertion order (dict-of-terms or ordered list).
    """
    terms: dict = field(default_factory=dict)

    def evaluate(self, env) -> list:
        out = []
        for _name, term in self.terms.items():
            out.extend(term.evaluate(env))
        return out

    def add(self, name: str, term: ObsTerm) -> "ObsGroup":
        self.terms[name] = term
        return self


# ── Standard observation functions ────────────────────────────────────────

def joint_pos_rel(env, asset_cfg: Optional[str] = None) -> list:
    """Joint positions relative to default (or absolute if no defaults)."""
    return list(env.get_joint_positions())


def joint_vel_rel(env, asset_cfg: Optional[str] = None) -> list:
    """Joint velocities."""
    return list(env.get_joint_velocities())


def base_lin_vel(env, asset_cfg: Optional[str] = None) -> list:
    """Base body linear velocity. For Cartpole the cart is treated as base."""
    pos = env.get_joint_positions()
    vel = env.get_joint_velocities()
    # Heuristic: first joint velocity component is the base linear vel (cart for Cartpole).
    # Real impl reads link_state but this matches the existing _state pattern.
    return [vel[0] if vel else 0.0, 0.0, 0.0]


def base_ang_vel(env, asset_cfg: Optional[str] = None) -> list:
    """Base body angular velocity. For Cartpole there is no rotation base."""
    return [0.0, 0.0, 0.0]


def last_action(env, asset_cfg: Optional[str] = None) -> list:
    """Most recently applied action (or [0,...] if none yet)."""
    return list(getattr(env, "_last_action", []) or [0.0])


def generated_commands(env, command_name: str = "default") -> list:
    """User-injected command vectors (target joint pose / velocity / pose).

    Stored on env via `env._commands[command_name] = [...]`; defaults to [].
    """
    commands = getattr(env, "_commands", {})
    return list(commands.get(command_name, []))


# ── Locomotion observation extensions (iter 61) ───────────────────────────


import math as _math
from typing import List as _List


def _quat_rotate_inverse(quat: tuple, vec: tuple) -> tuple:
    """Rotate a world-frame 3-vec into body frame: v_body = q⁻¹ v_world q.

    For unit quaternion (qx, qy, qz, qw), the inverse rotation negates the
    xyz part. Uses the iter 35 utils.math formula inlined here to keep mdp
    standalone (no cross-namespace imports).
    """
    qx, qy, qz, qw = quat
    qx, qy, qz = -qx, -qy, -qz   # inverse rotation = negate xyz
    vx, vy, vz = vec
    cx = qy * vz - qz * vy
    cy = qz * vx - qx * vz
    cz = qx * vy - qy * vx
    cx += qw * vx
    cy += qw * vy
    cz += qw * vz
    return (
        vx + 2.0 * (qy * cz - qz * cy),
        vy + 2.0 * (qz * cx - qx * cz),
        vz + 2.0 * (qx * cy - qy * cx),
    )


def _read_root_pos(env) -> tuple:
    """Read base position. Sources: env.root_position (iter 43) →
    env._base_pos → (0, 0, 0)."""
    p = getattr(env, "root_position", None)
    if p is not None and len(p) >= 3:
        return (p[0], p[1], p[2])
    p = getattr(env, "_base_pos", None)
    if p is not None and len(p) >= 3:
        return (p[0], p[1], p[2])
    return (0.0, 0.0, 0.0)


def _read_root_quat(env) -> tuple:
    """Read base orientation. Identity (0, 0, 0, 1) when unavailable."""
    q = getattr(env, "root_orientation", None)
    if q is not None and len(q) == 4:
        return (q[0], q[1], q[2], q[3])
    return (0.0, 0.0, 0.0, 1.0)


def _read_root_lin_vel_w(env) -> tuple:
    """World-frame base linear velocity. 3-source fallback chain."""
    v = getattr(env, "root_linear_velocity", None)
    if v is not None and len(v) >= 3:
        return (v[0], v[1], v[2])
    v = getattr(env, "_base_lin_vel", None) or getattr(env, "base_lin_vel_w_attr", None)
    if v is not None and len(v) >= 3:
        return (v[0], v[1], v[2])
    if hasattr(env, "get_joint_velocities"):
        dq = env.get_joint_velocities()
        return (dq[0] if dq else 0.0, 0.0, 0.0)
    return (0.0, 0.0, 0.0)


def _read_root_ang_vel_w(env) -> tuple:
    """World-frame base angular velocity. Same fallback chain."""
    v = getattr(env, "root_angular_velocity", None)
    if v is not None and len(v) >= 3:
        return (v[0], v[1], v[2])
    v = getattr(env, "_base_ang_vel", None)
    if v is not None and len(v) >= 3:
        return (v[0], v[1], v[2])
    return (0.0, 0.0, 0.0)


def base_pos_z(env, asset_cfg: Optional[str] = None) -> list:
    """Base z position (single scalar in a 1-element list).

    Standard input feature for legged locomotion — policy learns to
    maintain target standing height. Reads env.root_position[2].
    """
    return [_read_root_pos(env)[2]]


def base_lin_vel_w(env, asset_cfg: Optional[str] = None) -> list:
    """World-frame base linear velocity (3-vec). Use base_lin_vel_b for
    body-frame velocity (typical Isaac Lab convention for legged tasks)."""
    return list(_read_root_lin_vel_w(env))


def base_lin_vel_b(env, asset_cfg: Optional[str] = None) -> list:
    """Body-frame base linear velocity (3-vec). World velocity rotated
    into body frame via root orientation inverse.

    Standard observation for locomotion — the policy sees velocity in
    its own frame regardless of body yaw, making the learned controller
    yaw-invariant.
    """
    v_world = _read_root_lin_vel_w(env)
    quat = _read_root_quat(env)
    return list(_quat_rotate_inverse(quat, v_world))


def base_ang_vel_b(env, asset_cfg: Optional[str] = None) -> list:
    """Body-frame base angular velocity (3-vec)."""
    w_world = _read_root_ang_vel_w(env)
    quat = _read_root_quat(env)
    return list(_quat_rotate_inverse(quat, w_world))


def projected_gravity(env, asset_cfg: Optional[str] = None) -> list:
    """Projected gravity in body frame (3-vec, magnitude ≈ 1).

    Flat upright robot → (0, 0, -1). Tilted → first two components
    indicate roll / pitch direction. Critical observation for legged
    locomotion — policy uses this to maintain upright posture.
    """
    quat = _read_root_quat(env)
    return list(_quat_rotate_inverse(quat, (0.0, 0.0, -1.0)))


def joint_pos_rel_default(env, asset_cfg: Optional[str] = None) -> list:
    """Joint positions relative to the cfg-declared default pose.

    Reads env.cfg.default_joint_pos as list (one value per joint). Falls
    back to absolute joint positions when no default is configured.

    Used as a regularising obs feature — policy learns deviations from
    a known good pose (typically the "default standing" configuration).
    """
    q = env.get_joint_positions()
    cfg = getattr(env, "cfg", None)
    default = getattr(cfg, "default_joint_pos", None) if cfg else None
    if default is None:
        return list(q)
    return [q[i] - (default[i] if i < len(default) else 0.0)
            for i in range(len(q))]


def last_action_clipped(env, low: float = -1.0, high: float = 1.0,
                         asset_cfg: Optional[str] = None) -> list:
    """Most recent action clipped to (low, high). Standard input feature
    for action-aware policies (network sees its own previous action,
    encouraging smooth control)."""
    a = getattr(env, "_last_action", []) or []
    return [max(low, min(high, x)) for x in a]


def height_scan(
    env,
    sensor_name: str = "",
    offset: float = 0.0,
    asset_cfg: Optional[str] = None,
) -> list:
    """Read a height-scan ray sensor (iter 34 RayCaster) relative to
    base height. Returns a flat list of per-ray Δheight.

    Reads from `env.height_scanners[sensor_name]` (typical iter 27
    InteractiveScene mount). Falls back to `env.scene.get_latest_observation
    (0, sensor_name)` for iter 28 auto-sample cache.

    `offset` shifts the per-ray hit z by a constant (e.g. foot offset
    above the heightfield). Returns empty list when no sensor wired —
    permissive for cfg portability.
    """
    if not sensor_name:
        return []
    # Direct mount: env.height_scanners[name].get_height_scan().
    scanners = getattr(env, "height_scanners", None)
    if isinstance(scanners, dict) and sensor_name in scanners:
        scanner = scanners[sensor_name]
        if hasattr(scanner, "get_height_scan"):
            base_pos = _read_root_pos(env)
            base_quat = _read_root_quat(env)
            heights = scanner.get_height_scan(
                link_pos=base_pos, link_quat=base_quat,
            )
            return [
                (base_pos[2] - h - offset)
                if _math.isfinite(h) else 0.0
                for h in heights
            ]
    # Iter 28 InteractiveScene cache: scene.get_latest_observation.
    scene = getattr(env, "scene", None)
    if scene is not None and hasattr(scene, "get_latest_observation"):
        reading = scene.get_latest_observation(0, sensor_name)
        if reading is not None and hasattr(reading, "__iter__"):
            # Lidar returns a list of LidarReturn objects with .range.
            base_z = _read_root_pos(env)[2]
            out: _List[float] = []
            for r in reading:
                rng = getattr(r, "range", None)
                if rng is None or not _math.isfinite(rng):
                    out.append(0.0)
                else:
                    out.append(base_z - rng - offset)
            return out
    return []
