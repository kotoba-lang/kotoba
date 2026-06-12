"""isaaclab.utils.math — quaternion + Euler + frame-transform helpers.

Mirror of `isaaclab.utils.math` (Isaac Lab 1.x). Public-API drop-in subset:
quaternion algebra, Euler ↔ quaternion conversion, axis-angle ↔ quaternion,
slerp, random quaternion, plus frame composition helpers.

Convention: quaternions are stored as `(x, y, z, w)` tuples (matches the
glam / Isaac Sim Quat layout used elsewhere in nv_compat — `isaacsim.sensors.imu`
+ `isaaclab.sensors.ray_caster`). All angles in radians.

Frame transforms: a "transform" is (pos, quat) — translation in world frame
+ rotation as quaternion. `combine_frame_transforms` computes the world-
frame pose of a child whose offset is expressed in the parent's frame.
`subtract_frame_transforms` computes the relative pose of B as seen from A.

Pure stdlib (math + random for the seedable quat_random). Replicates the
PyTorch / NumPy semantics of the upstream module at the scalar level so
users can port functional code by changing the import path only.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple


# ────────────────────────────────────────────────────────────────────────────
# 3-vec primitives
# ────────────────────────────────────────────────────────────────────────────


def normalize3(v: tuple) -> tuple:
    """Returns v / |v|. Zero-length vectors return (0, 0, 0)."""
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if n < 1e-12:
        return (0.0, 0.0, 0.0)
    return (v[0] / n, v[1] / n, v[2] / n)


def dot3(a: tuple, b: tuple) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross3(a: tuple, b: tuple) -> tuple:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def vec_add(a: tuple, b: tuple) -> tuple:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vec_sub(a: tuple, b: tuple) -> tuple:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vec_scale(v: tuple, s: float) -> tuple:
    return (v[0] * s, v[1] * s, v[2] * s)


# ────────────────────────────────────────────────────────────────────────────
# Quaternion algebra
# ────────────────────────────────────────────────────────────────────────────


def quat_identity() -> tuple:
    return (0.0, 0.0, 0.0, 1.0)


def quat_normalize(q: tuple) -> tuple:
    """Normalize quaternion to unit length. Identity-ish if input is degenerate."""
    qx, qy, qz, qw = q
    n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    if n < 1e-12:
        return quat_identity()
    return (qx / n, qy / n, qz / n, qw / n)


def quat_conjugate(q: tuple) -> tuple:
    return (-q[0], -q[1], -q[2], q[3])


def quat_inverse(q: tuple) -> tuple:
    """For unit quaternions, inverse = conjugate. Includes a 1/|q|² scale to
    handle non-unit inputs correctly."""
    qx, qy, qz, qw = q
    n2 = qx * qx + qy * qy + qz * qz + qw * qw
    if n2 < 1e-24:
        return quat_identity()
    inv = 1.0 / n2
    return (-qx * inv, -qy * inv, -qz * inv, qw * inv)


def quat_mul(q1: tuple, q2: tuple) -> tuple:
    """Hamilton product q1 * q2 (apply q2 then q1)."""
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2
    return (
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
    )


def quat_rotate(q: tuple, v: tuple) -> tuple:
    """Rotate a 3-vec by a unit quaternion: v' = q v q^-1."""
    qx, qy, qz, qw = q
    vx, vy, vz = v
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


def quat_rotate_inverse(q: tuple, v: tuple) -> tuple:
    """Rotate a 3-vec by the inverse of `q`. Equivalent to
    `quat_rotate(quat_conjugate(q), v)` for unit quaternions."""
    return quat_rotate(quat_conjugate(q), v)


def quat_apply(q: tuple, v: tuple) -> tuple:
    """Alias of `quat_rotate` for code that follows Isaac Lab naming."""
    return quat_rotate(q, v)


def quat_dot(q1: tuple, q2: tuple) -> float:
    return q1[0] * q2[0] + q1[1] * q2[1] + q1[2] * q2[2] + q1[3] * q2[3]


def quat_diff(q1: tuple, q2: tuple) -> tuple:
    """Difference quaternion: q_diff such that q2 = q_diff * q1.

    Equivalent to `quat_mul(q2, quat_inverse(q1))`. Useful for measuring
    "how much rotation gets you from q1 to q2".
    """
    return quat_mul(q2, quat_inverse(q1))


# ────────────────────────────────────────────────────────────────────────────
# Euler / axis-angle / yaw extractors
# ────────────────────────────────────────────────────────────────────────────


def quat_from_angle_axis(angle: float, axis: tuple) -> tuple:
    """Build a unit quaternion that rotates by `angle` radians around `axis`."""
    ax = normalize3(axis)
    if ax == (0.0, 0.0, 0.0):
        return quat_identity()
    half = angle * 0.5
    s = math.sin(half)
    return (ax[0] * s, ax[1] * s, ax[2] * s, math.cos(half))


def axis_angle_from_quat(q: tuple) -> Tuple[tuple, float]:
    """Returns (axis, angle) such that quat_from_angle_axis(angle, axis) = q.

    Axis is returned as a unit vector; angle is in (-π, π]. For the identity
    quaternion the axis is (0, 0, 1) and angle is 0.
    """
    qn = quat_normalize(q)
    qx, qy, qz, qw = qn
    # Clamp for numerical safety.
    qw = max(-1.0, min(1.0, qw))
    angle = 2.0 * math.acos(qw)
    s = math.sqrt(max(0.0, 1.0 - qw * qw))
    if s < 1e-8:
        return ((0.0, 0.0, 1.0), 0.0)
    axis = (qx / s, qy / s, qz / s)
    # Wrap angle to (-π, π].
    if angle > math.pi:
        angle -= 2.0 * math.pi
        axis = (-axis[0], -axis[1], -axis[2])
    return (axis, angle)


def quat_from_euler_xyz(roll: float, pitch: float, yaw: float) -> tuple:
    """Build a quaternion from intrinsic Tait-Bryan angles (x-y-z order:
    roll about x, pitch about y, yaw about z; applied in that order)."""
    hr, hp, hy = roll * 0.5, pitch * 0.5, yaw * 0.5
    cr, sr = math.cos(hr), math.sin(hr)
    cp, sp = math.cos(hp), math.sin(hp)
    cy, sy = math.cos(hy), math.sin(hy)
    return (
        sr * cp * cy - cr * sp * sy,  # x
        cr * sp * cy + sr * cp * sy,  # y
        cr * cp * sy - sr * sp * cy,  # z
        cr * cp * cy + sr * sp * sy,  # w
    )


def euler_xyz_from_quat(q: tuple) -> Tuple[float, float, float]:
    """Extract (roll, pitch, yaw) from a quaternion.

    Roll = atan2(2(wx + yz), 1 - 2(x² + y²))
    Pitch = asin(2(wy - zx))                            # clamped
    Yaw  = atan2(2(wz + xy), 1 - 2(y² + z²))
    """
    qx, qy, qz, qw = quat_normalize(q)
    # Roll (x-axis rotation).
    sinr_cosp = 2.0 * (qw * qx + qy * qz)
    cosr_cosp = 1.0 - 2.0 * (qx * qx + qy * qy)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    # Pitch (y-axis rotation).
    sinp = 2.0 * (qw * qy - qz * qx)
    sinp = max(-1.0, min(1.0, sinp))
    pitch = math.asin(sinp)
    # Yaw (z-axis rotation).
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    return (roll, pitch, yaw)


def quat_yaw_only(q: tuple) -> tuple:
    """Extract just the yaw component of `q` as a yaw-only quaternion.

    Canonical for foot-mount sensor scans that should stay world-aligned
    regardless of foot roll/pitch.
    """
    qx, qy, qz, qw = q
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    half = yaw * 0.5
    return (0.0, 0.0, math.sin(half), math.cos(half))


# ────────────────────────────────────────────────────────────────────────────
# Interpolation + random
# ────────────────────────────────────────────────────────────────────────────


def quat_slerp(q1: tuple, q2: tuple, t: float) -> tuple:
    """Spherical linear interpolation. t=0 → q1, t=1 → q2."""
    q1n = quat_normalize(q1)
    q2n = quat_normalize(q2)
    d = quat_dot(q1n, q2n)
    # Use the shortest arc (negate q2 if dot product is negative).
    if d < 0.0:
        q2n = (-q2n[0], -q2n[1], -q2n[2], -q2n[3])
        d = -d
    # Linear lerp + renormalize when very close (avoids 1/sin(θ) blow-up).
    if d > 0.9995:
        return quat_normalize((
            q1n[0] + t * (q2n[0] - q1n[0]),
            q1n[1] + t * (q2n[1] - q1n[1]),
            q1n[2] + t * (q2n[2] - q1n[2]),
            q1n[3] + t * (q2n[3] - q1n[3]),
        ))
    theta = math.acos(max(-1.0, min(1.0, d)))
    sin_t = math.sin(theta)
    a = math.sin((1.0 - t) * theta) / sin_t
    b = math.sin(t * theta) / sin_t
    return (
        a * q1n[0] + b * q2n[0],
        a * q1n[1] + b * q2n[1],
        a * q1n[2] + b * q2n[2],
        a * q1n[3] + b * q2n[3],
    )


def quat_random(rng_uniform: callable) -> tuple:
    """Uniformly random quaternion via Marsaglia (1972). Pass a `next_u01`
    callable; e.g. `_Lcg.next_u01` from the algos / envs modules."""
    # Sample two points in the unit disk.
    while True:
        x1 = 2.0 * rng_uniform() - 1.0
        y1 = 2.0 * rng_uniform() - 1.0
        s1 = x1 * x1 + y1 * y1
        if s1 < 1.0:
            break
    while True:
        x2 = 2.0 * rng_uniform() - 1.0
        y2 = 2.0 * rng_uniform() - 1.0
        s2 = x2 * x2 + y2 * y2
        if s2 < 1.0:
            break
    fac = math.sqrt((1.0 - s1) / s2)
    return (x1, y1, x2 * fac, y2 * fac)


def wrap_to_pi(angle: float) -> float:
    """Wrap `angle` to [-π, π) — matches `isaaclab.utils.math.wrap_to_pi`
    semantics (PyTorch remainder)."""
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


# ────────────────────────────────────────────────────────────────────────────
# Frame transforms (compose / decompose)
# ────────────────────────────────────────────────────────────────────────────


def combine_frame_transforms(
    t01: tuple, q01: tuple,
    t12: Optional[tuple] = None, q12: Optional[tuple] = None,
) -> Tuple[tuple, tuple]:
    """Compose two transforms: world←0 + 0←2 → world←2.

    Mirror of `isaaclab.utils.math.combine_frame_transforms`. `(t01, q01)`
    is the world-frame pose of frame 0; `(t12, q12)` is the pose of frame
    2 expressed in frame 0. Returns the world-frame pose of frame 2.

    With `t12` / `q12` defaulting to identity, this returns `(t01, q01)`.
    """
    if t12 is None:
        t12 = (0.0, 0.0, 0.0)
    if q12 is None:
        q12 = quat_identity()
    # Translation: t02 = t01 + R01 @ t12
    t02 = vec_add(t01, quat_rotate(q01, t12))
    # Rotation: q02 = q01 * q12
    q02 = quat_mul(q01, q12)
    return t02, q02


def subtract_frame_transforms(
    t01: tuple, q01: tuple,
    t02: tuple, q02: tuple,
) -> Tuple[tuple, tuple]:
    """Inverse of `combine_frame_transforms`: given world←0 and world←2,
    return 0←2 (the pose of frame 2 expressed in frame 0).

    Mirror of `isaaclab.utils.math.subtract_frame_transforms`.
    """
    q01_inv = quat_inverse(q01)
    t12 = quat_rotate(q01_inv, vec_sub(t02, t01))
    q12 = quat_mul(q01_inv, q02)
    return t12, q12


# ────────────────────────────────────────────────────────────────────────────
# Convenience batch helpers
# ────────────────────────────────────────────────────────────────────────────


def quaternions_close(q1: tuple, q2: tuple, atol: float = 1e-6) -> bool:
    """True if q1 and q2 represent the same rotation (handles ±q ambiguity)."""
    d = quat_dot(quat_normalize(q1), quat_normalize(q2))
    return abs(abs(d) - 1.0) < atol


def quat_to_rotation_matrix(q: tuple) -> List[List[float]]:
    """3×3 row-major rotation matrix from a unit quaternion."""
    qx, qy, qz, qw = quat_normalize(q)
    xx, yy, zz = qx * qx, qy * qy, qz * qz
    xy, xz, yz = qx * qy, qx * qz, qy * qz
    wx, wy, wz = qw * qx, qw * qy, qw * qz
    return [
        [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz),       2.0 * (xz + wy)],
        [2.0 * (xy + wz),       1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
        [2.0 * (xz - wy),       2.0 * (yz + wx),       1.0 - 2.0 * (xx + yy)],
    ]


def rotation_matrix_to_quat(m: List[List[float]]) -> tuple:
    """Quaternion from a 3×3 row-major rotation matrix (Shepperd's method)."""
    m00, m01, m02 = m[0]
    m10, m11, m12 = m[1]
    m20, m21, m22 = m[2]
    tr = m00 + m11 + m22
    if tr > 0.0:
        s = 0.5 / math.sqrt(tr + 1.0)
        return ((m21 - m12) * s, (m02 - m20) * s, (m10 - m01) * s, 0.25 / s)
    if m00 > m11 and m00 > m22:
        s = 2.0 * math.sqrt(1.0 + m00 - m11 - m22)
        return (0.25 * s, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s)
    if m11 > m22:
        s = 2.0 * math.sqrt(1.0 + m11 - m00 - m22)
        return ((m01 + m10) / s, 0.25 * s, (m12 + m21) / s, (m02 - m20) / s)
    s = 2.0 * math.sqrt(1.0 + m22 - m00 - m11)
    return ((m02 + m20) / s, (m12 + m21) / s, 0.25 * s, (m10 - m01) / s)
