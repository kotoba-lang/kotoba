"""isaacsim.sensors.Camera mirror — pinhole projection + depth image.

Tracks 40-engine/kami-engine/kami-sensor-sim/src/camera.rs formulas line-for-
line so Pyodide / native CPython callers get identical numeric output.
stdlib-only (math).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CameraIntrinsics:
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int
    near: float = 0.05
    far: float = 1000.0

    @classmethod
    def from_hfov(cls, width: int, height: int, hfov_rad: float) -> "CameraIntrinsics":
        fx = (width / 2.0) / math.tan(hfov_rad / 2.0)
        return cls(fx=fx, fy=fx, cx=width / 2.0, cy=height / 2.0,
                   width=width, height=height)


@dataclass
class Projection:
    u: int
    v: int
    depth: float


@dataclass
class DepthImage:
    width: int
    height: int
    pixels: list  # row-major, len = width * height

    @classmethod
    def empty(cls, width: int, height: int) -> "DepthImage":
        return cls(width=width, height=height,
                   pixels=[math.inf] * (width * height))

    def at(self, u: int, v: int) -> Optional[float]:
        if u < 0 or v < 0 or u >= self.width or v >= self.height:
            return None
        return self.pixels[v * self.width + u]

    def populated_count(self) -> int:
        return sum(1 for d in self.pixels if math.isfinite(d))


def _transform_point(view: list, p: tuple[float, float, float]) -> tuple[float, float, float]:
    """Apply a 3x4 (row-major) world→camera affine to a world point."""
    x = view[0] * p[0] + view[1] * p[1] + view[2] * p[2] + view[3]
    y = view[4] * p[0] + view[5] * p[1] + view[6] * p[2] + view[7]
    z = view[8] * p[0] + view[9] * p[1] + view[10] * p[2] + view[11]
    return (x, y, z)


@dataclass
class Camera:
    name: str
    prim_path: str
    intrinsics: CameraIntrinsics
    # 3x4 row-major world→camera affine (identity by default).
    view: list = field(default_factory=lambda: [1.0, 0.0, 0.0, 0.0,
                                                 0.0, 1.0, 0.0, 0.0,
                                                 0.0, 0.0, 1.0, 0.0])

    def set_view(self, view: list) -> None:
        if len(view) != 12:
            raise ValueError("view must be a 3x4 row-major affine (12 floats)")
        self.view = list(view)

    def look_at(self, eye: tuple[float, float, float],
                target: tuple[float, float, float],
                up: tuple[float, float, float] = (0.0, 1.0, 0.0)) -> None:
        """Mirror of kami_sensor_sim::Camera::look_at."""
        ex, ey, ez = eye
        tx, ty, tz = target
        ux, uy, uz = up
        # forward = (target - eye).normalize()
        fx, fy, fz = tx - ex, ty - ey, tz - ez
        n = math.sqrt(fx*fx + fy*fy + fz*fz)
        fx, fy, fz = fx / n, fy / n, fz / n
        # right = forward.cross(up).normalize()
        rx = fy * uz - fz * uy
        ry = fz * ux - fx * uz
        rz = fx * uy - fy * ux
        n = math.sqrt(rx*rx + ry*ry + rz*rz)
        rx, ry, rz = rx / n, ry / n, rz / n
        # new_up = right.cross(forward)
        nx = ry * fz - rz * fy
        ny = rz * fx - rx * fz
        nz = rx * fy - ry * fx
        # OpenCV camera basis (rows of world→camera rotation):
        #   row0 = right       (cam +x)
        #   row1 = -new_up     (cam +y is image-down)
        #   row2 = forward     (cam +z)
        r00, r01, r02 = rx, ry, rz
        r10, r11, r12 = -nx, -ny, -nz
        r20, r21, r22 = fx, fy, fz
        t0 = -(r00 * ex + r01 * ey + r02 * ez)
        t1 = -(r10 * ex + r11 * ey + r12 * ez)
        t2 = -(r20 * ex + r21 * ey + r22 * ez)
        self.view = [r00, r01, r02, t0,
                     r10, r11, r12, t1,
                     r20, r21, r22, t2]

    def project_world_point(self, p_world: tuple[float, float, float]) -> Optional[Projection]:
        cx_, cy_, cz_ = _transform_point(self.view, p_world)
        depth = cz_
        if depth <= self.intrinsics.near or depth >= self.intrinsics.far:
            return None
        u_f = self.intrinsics.fx * (cx_ / depth) + self.intrinsics.cx
        v_f = self.intrinsics.fy * (cy_ / depth) + self.intrinsics.cy
        if not (math.isfinite(u_f) and math.isfinite(v_f)):
            return None
        if u_f < 0.0 or v_f < 0.0:
            return None
        u = math.floor(u_f)
        v = math.floor(v_f)
        if u >= self.intrinsics.width or v >= self.intrinsics.height:
            return None
        return Projection(u=int(u), v=int(v), depth=depth)

    def render_points_to_depth_image(self, points: list) -> DepthImage:
        img = DepthImage.empty(self.intrinsics.width, self.intrinsics.height)
        for p in points:
            proj = self.project_world_point(tuple(p))
            if proj is None:
                continue
            idx = proj.v * self.intrinsics.width + proj.u
            if proj.depth < img.pixels[idx]:
                img.pixels[idx] = proj.depth
        return img
