"""isaacsim.sensors.RotatingLidarPhysX mirror — analytic raycast lidar.

ROS REP-105 sensor frame (+x forward, +y left, +z up; Isaac Sim lidar default).
Tracks 40-engine/kami-engine/kami-sensor-sim/src/lidar.rs formulas line-for-
line so Pyodide / native CPython callers get identical numeric output.
stdlib-only (math).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


@dataclass
class LidarIntrinsics:
    hfov: float
    vfov: float
    h_beams: int
    v_beams: int
    range_min: float = 0.5
    range_max: float = 100.0

    @classmethod
    def vlp16(cls) -> "LidarIntrinsics":
        return cls(hfov=2 * math.pi, vfov=math.radians(30),
                   h_beams=1800, v_beams=16, range_min=0.5, range_max=100.0)

    @classmethod
    def toy(cls) -> "LidarIntrinsics":
        return cls(hfov=math.pi / 2.0, vfov=math.radians(30),
                   h_beams=8, v_beams=4, range_min=0.05, range_max=50.0)


class PrimKind(Enum):
    GROUND_PLANE = auto()
    SPHERE = auto()
    AABB = auto()


@dataclass
class Primitive:
    kind: PrimKind
    # for GROUND_PLANE: height
    # for SPHERE: center (3-tuple), radius
    # for AABB: min (3-tuple), max (3-tuple)
    height: float = 0.0
    center: tuple = (0.0, 0.0, 0.0)
    radius: float = 1.0
    min: tuple = (0.0, 0.0, 0.0)
    max: tuple = (0.0, 0.0, 0.0)

    @staticmethod
    def ground_plane(height: float) -> "Primitive":
        return Primitive(kind=PrimKind.GROUND_PLANE, height=height)

    @staticmethod
    def sphere(center: tuple, radius: float) -> "Primitive":
        return Primitive(kind=PrimKind.SPHERE, center=center, radius=radius)

    @staticmethod
    def aabb(mn: tuple, mx: tuple) -> "Primitive":
        return Primitive(kind=PrimKind.AABB, min=mn, max=mx)

    def intersect(self, origin: tuple, dir_: tuple) -> Optional[float]:
        ox, oy, oz = origin
        dx, dy, dz = dir_
        if self.kind == PrimKind.GROUND_PLANE:
            if abs(dz) < 1e-6:
                return None
            t = (self.height - oz) / dz
            return t if t > 0.0 else None
        elif self.kind == PrimKind.SPHERE:
            cx, cy, cz = self.center
            ocx, ocy, ocz = ox - cx, oy - cy, oz - cz
            b = ocx * dx + ocy * dy + ocz * dz
            c = ocx * ocx + ocy * ocy + ocz * ocz - self.radius * self.radius
            disc = b * b - c
            if disc < 0.0:
                return None
            sq = math.sqrt(disc)
            t0 = -b - sq
            t1 = -b + sq
            if t0 > 1e-4:
                return t0
            if t1 > 1e-4:
                return t1
            return None
        elif self.kind == PrimKind.AABB:
            inv = (1.0 / dx if dx != 0 else float("inf"),
                   1.0 / dy if dy != 0 else float("inf"),
                   1.0 / dz if dz != 0 else float("inf"))
            t1x = (self.min[0] - ox) * inv[0]
            t2x = (self.max[0] - ox) * inv[0]
            t1y = (self.min[1] - oy) * inv[1]
            t2y = (self.max[1] - oy) * inv[1]
            t1z = (self.min[2] - oz) * inv[2]
            t2z = (self.max[2] - oz) * inv[2]
            tmin = max(min(t1x, t2x), min(t1y, t2y), min(t1z, t2z))
            tmax = min(max(t1x, t2x), max(t1y, t2y), max(t1z, t2z))
            if tmax < 0.0 or tmin > tmax:
                return None
            if tmin > 1e-4:
                return tmin
            if tmax > 1e-4:
                return tmax
            return None
        return None


@dataclass
class Scene:
    primitives: list = field(default_factory=list)

    def add(self, p: Primitive) -> "Scene":
        self.primitives.append(p)
        return self

    def nearest_hit(self, origin: tuple, dir_: tuple) -> Optional[tuple]:
        best: Optional[tuple] = None
        for i, p in enumerate(self.primitives):
            t = p.intersect(origin, dir_)
            if t is not None and (best is None or t < best[0]):
                best = (t, i)
        return best


@dataclass
class LidarReturn:
    range: float
    point_sensor: tuple
    prim_index: int


def _transform_point(view: list, p: tuple) -> tuple:
    x = view[0] * p[0] + view[1] * p[1] + view[2] * p[2] + view[3]
    y = view[4] * p[0] + view[5] * p[1] + view[6] * p[2] + view[7]
    z = view[8] * p[0] + view[9] * p[1] + view[10] * p[2] + view[11]
    return (x, y, z)


def _transform_vector(view: list, v: tuple) -> tuple:
    return (view[0] * v[0] + view[1] * v[1] + view[2] * v[2],
            view[4] * v[0] + view[5] * v[1] + view[6] * v[2],
            view[8] * v[0] + view[9] * v[1] + view[10] * v[2])


def _invert_affine_3x4(m: list) -> list:
    """Invert a rigid 3x4 affine (R | t). Assumes R is orthonormal."""
    r = [m[0], m[1], m[2], m[4], m[5], m[6], m[8], m[9], m[10]]
    # R^T (transpose of 3x3 rotation)
    rt = [r[0], r[3], r[6], r[1], r[4], r[7], r[2], r[5], r[8]]
    t = (m[3], m[7], m[11])
    nt = (-(rt[0] * t[0] + rt[1] * t[1] + rt[2] * t[2]),
          -(rt[3] * t[0] + rt[4] * t[1] + rt[5] * t[2]),
          -(rt[6] * t[0] + rt[7] * t[1] + rt[8] * t[2]))
    return [rt[0], rt[1], rt[2], nt[0],
            rt[3], rt[4], rt[5], nt[1],
            rt[6], rt[7], rt[8], nt[2]]


@dataclass
class Lidar:
    name: str
    prim_path: str
    intrinsics: LidarIntrinsics
    view: list = field(default_factory=lambda: [1.0, 0.0, 0.0, 0.0,
                                                 0.0, 1.0, 0.0, 0.0,
                                                 0.0, 0.0, 1.0, 0.0])

    def _beam_dir_sensor(self, i_h: int, i_v: int) -> tuple:
        i = self.intrinsics
        az_min = -i.hfov * 0.5
        el_min = -i.vfov * 0.5
        az_step = i.hfov / i.h_beams if i.h_beams > 1 else 0.0
        el_step = i.vfov / i.v_beams if i.v_beams > 1 else 0.0
        az = az_min + (i_h + 0.5) * az_step
        el = el_min + (i_v + 0.5) * el_step
        sa, ca = math.sin(az), math.cos(az)
        se, ce = math.sin(el), math.cos(el)
        return (ce * ca, ce * sa, se)

    def acquire_data(self, scene: Scene) -> list:
        s2w = _invert_affine_3x4(self.view)
        origin_world = _transform_point(s2w, (0.0, 0.0, 0.0))
        out: list = []
        for v in range(self.intrinsics.v_beams):
            for h in range(self.intrinsics.h_beams):
                dir_sensor = self._beam_dir_sensor(h, v)
                dir_world = _transform_vector(s2w, dir_sensor)
                # Normalize dir_world (rotation should preserve length but be safe)
                n = math.sqrt(sum(x * x for x in dir_world))
                if n < 1e-12:
                    out.append(LidarReturn(range=math.inf, point_sensor=(0, 0, 0),
                                           prim_index=-1))
                    continue
                dir_world = (dir_world[0] / n, dir_world[1] / n, dir_world[2] / n)
                hit = scene.nearest_hit(origin_world, dir_world)
                if hit is None or not (self.intrinsics.range_min <= hit[0] <= self.intrinsics.range_max):
                    out.append(LidarReturn(range=math.inf, point_sensor=(0, 0, 0),
                                           prim_index=-1))
                else:
                    t, idx = hit
                    out.append(LidarReturn(
                        range=t,
                        point_sensor=(dir_sensor[0] * t, dir_sensor[1] * t, dir_sensor[2] * t),
                        prim_index=idx,
                    ))
        return out
