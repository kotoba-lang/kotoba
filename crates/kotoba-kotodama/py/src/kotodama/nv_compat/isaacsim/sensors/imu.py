"""isaacsim.sensors.IMUSensor mirror — body-frame IMU.

Reports proper acceleration (inertial − gravity) in body frame + angular
velocity in body frame + orientation. Convention matches the Rust crate
kami-sensor-sim::Imu line-for-line.

Quaternions: stored as (x, y, z, w) tuples (glam Quat layout).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# ----- quaternion helpers (stdlib only) -----

def quat_identity() -> tuple:
    return (0.0, 0.0, 0.0, 1.0)


def quat_from_axis_angle(axis: tuple, angle: float) -> tuple:
    n = math.sqrt(axis[0] ** 2 + axis[1] ** 2 + axis[2] ** 2)
    if n < 1e-12:
        return quat_identity()
    s = math.sin(angle / 2.0) / n
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(angle / 2.0))


def quat_inverse(q: tuple) -> tuple:
    # for unit quaternions, inverse = conjugate
    return (-q[0], -q[1], -q[2], q[3])


def quat_rotate_vec(q: tuple, v: tuple) -> tuple:
    # apply quaternion rotation to a 3-vector: v' = q v q^-1
    qx, qy, qz, qw = q
    vx, vy, vz = v
    # cross1 = q.xyz × v
    cx = qy * vz - qz * vy
    cy = qz * vx - qx * vz
    cz = qx * vy - qy * vx
    # cross1 += w * v
    cx += qw * vx
    cy += qw * vy
    cz += qw * vz
    # result = v + 2 * (q.xyz × cross1)
    rx = vx + 2.0 * (qy * cz - qz * cy)
    ry = vy + 2.0 * (qz * cx - qx * cz)
    rz = vz + 2.0 * (qx * cy - qy * cx)
    return (rx, ry, rz)


@dataclass
class ImuReading:
    linear_acceleration: tuple = (0.0, 0.0, 0.0)
    angular_velocity: tuple = (0.0, 0.0, 0.0)
    orientation: tuple = field(default_factory=quat_identity)
    time: float = 0.0


@dataclass
class Imu:
    name: str
    prim_path: str
    link_name: str
    gravity: tuple = (0.0, 0.0, -9.81)

    _last_lin_vel_world: tuple = (0.0, 0.0, 0.0)
    _last_time: float = 0.0
    _has_previous: bool = False

    def set_gravity(self, g: tuple) -> None:
        self.gravity = g

    def reset(self) -> None:
        self._has_previous = False
        self._last_lin_vel_world = (0.0, 0.0, 0.0)
        self._last_time = 0.0

    def sample(self, lin_vel_world: tuple, ang_vel_world: tuple,
               orientation: tuple, time: float) -> ImuReading:
        if self._has_previous and time > self._last_time:
            dt = time - self._last_time
            ax = (lin_vel_world[0] - self._last_lin_vel_world[0]) / dt
            ay = (lin_vel_world[1] - self._last_lin_vel_world[1]) / dt
            az = (lin_vel_world[2] - self._last_lin_vel_world[2]) / dt
            inertial = (ax, ay, az)
        else:
            inertial = (0.0, 0.0, 0.0)
        proper = (inertial[0] - self.gravity[0],
                  inertial[1] - self.gravity[1],
                  inertial[2] - self.gravity[2])
        inv = quat_inverse(orientation)
        lin_accel_body = quat_rotate_vec(inv, proper)
        ang_vel_body = quat_rotate_vec(inv, ang_vel_world)

        self._last_lin_vel_world = lin_vel_world
        self._last_time = time
        self._has_previous = True

        return ImuReading(
            linear_acceleration=lin_accel_body,
            angular_velocity=ang_vel_body,
            orientation=orientation,
            time=time,
        )
