"""isaacsim.sensors.ContactSensor mirror — sphere-vs-primitive contact.

Tracks 40-engine/kami-engine/kami-sensor-sim/src/contact.rs formula-for-formula.
Each articulation link is approximated as a sphere; at sample time the sensor
walks the scene primitives (GroundPlane / Sphere / AABB from lidar facade) and
reports in_contact / penetration_depth / contact_normal / closest_distance /
closest_primitive.
stdlib-only (math).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .lidar import PrimKind, Primitive, Scene


@dataclass
class ContactReading:
    in_contact: bool = False
    penetration_depth: float = 0.0
    contact_normal: tuple = (0.0, 0.0, 1.0)
    closest_distance: float = float("inf")
    closest_primitive: int = -1
    time: float = 0.0


def _primitive_closest(prim: Primitive, p: tuple) -> tuple:
    """Returns (signed_distance, outward_normal). Signed distance < 0 when
    p is inside the primitive."""
    px, py, pz = p
    if prim.kind == PrimKind.GROUND_PLANE:
        d = pz - prim.height
        return (d, (0.0, 0.0, 1.0))
    elif prim.kind == PrimKind.SPHERE:
        cx, cy, cz = prim.center
        dx, dy, dz = px - cx, py - cy, pz - cz
        d_centers = math.sqrt(dx * dx + dy * dy + dz * dz)
        if d_centers < 1e-12:
            return (-prim.radius, (0.0, 0.0, 1.0))
        n = (dx / d_centers, dy / d_centers, dz / d_centers)
        return (d_centers - prim.radius, n)
    elif prim.kind == PrimKind.AABB:
        cx = max(prim.min[0], min(prim.max[0], px))
        cy = max(prim.min[1], min(prim.max[1], py))
        cz = max(prim.min[2], min(prim.max[2], pz))
        clamped = (cx, cy, cz)
        if clamped == p:
            # Inside the box; pick nearest face by depth.
            depths = [
                (px - prim.min[0], (-1.0, 0.0, 0.0)),
                (prim.max[0] - px, (1.0, 0.0, 0.0)),
                (py - prim.min[1], (0.0, -1.0, 0.0)),
                (prim.max[1] - py, (0.0, 1.0, 0.0)),
                (pz - prim.min[2], (0.0, 0.0, -1.0)),
                (prim.max[2] - pz, (0.0, 0.0, 1.0)),
            ]
            min_depth, normal = min(depths, key=lambda x: x[0])
            return (-min_depth, normal)
        else:
            dx, dy, dz = px - cx, py - cy, pz - cz
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
            if d < 1e-12:
                return (0.0, (0.0, 0.0, 1.0))
            return (d, (dx / d, dy / d, dz / d))
    return (float("inf"), (0.0, 0.0, 1.0))


@dataclass
class ContactSensor:
    name: str
    prim_path: str
    link_name: str
    radius: float = 1.0

    def sample(self, link_position: tuple, scene: Scene, time: float = 0.0) -> ContactReading:
        closest_d = float("inf")
        closest_idx = -1
        closest_normal = (0.0, 0.0, 1.0)
        for i, prim in enumerate(scene.primitives):
            d, n = _primitive_closest(prim, link_position)
            sphere_surface_d = d - self.radius
            if sphere_surface_d < closest_d:
                closest_d = sphere_surface_d
                closest_idx = i
                closest_normal = n
        in_contact = closest_d < 0.0
        pen = -closest_d if in_contact else 0.0
        return ContactReading(
            in_contact=in_contact,
            penetration_depth=pen,
            contact_normal=closest_normal,
            closest_distance=closest_d,
            closest_primitive=closest_idx,
            time=time,
        )
