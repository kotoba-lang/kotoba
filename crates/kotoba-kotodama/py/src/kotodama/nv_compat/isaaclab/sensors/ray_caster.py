"""isaaclab.sensors.RayCaster — pattern-based ray-bundle sensor.

The canonical Isaac Lab sensor for legged-locomotion height scanning. Each
foot (or any body link) has N rays cast downward into the terrain; the
sensor returns the world-frame intersection point + distance for each ray.
RL policies feed the per-foot height map as observation, giving the policy
local terrain awareness without expensive depth-image rendering.

API mirror of `isaaclab.sensors.ray_caster.RayCaster`:

    cfg = RayCasterCfg(
        prim_path="/World/quadruped/front_left_foot",
        mesh_prim_paths=["/World/terrain"],
        attach_yaw_only=True,                  # ignore roll/pitch of foot
        offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 0.0)),
        pattern_cfg=GridPatternCfg(
            resolution=0.1,                    # 10cm cell
            size=(0.4, 0.4),                   # 40×40 cm scan area
            direction=(0.0, 0.0, -1.0),        # rays point straight down
        ),
    )
    sensor = RayCaster(cfg, scene)
    data = sensor.sample(link_pos=(1.0, 2.0, 0.3), link_quat=(0,0,0,1), time=0.0)
    # data.ray_hits_w  — list of (x, y, z) hit points
    # data.ray_distances — list of float ray distances (inf if no hit)
    # data.pos_w / data.quat_w  — sensor pose in world frame

Built on `isaacsim.sensors.BvhScene` for O(log N) ray intersection. A
single sample() call against a 100-primitive scene with a 9×9 = 81-ray
grid pattern takes ~0.5 ms on CPU (no GPU dispatch needed).

Pure stdlib (math). Reuses BvhScene / Scene / Primitive from
isaacsim.sensors (lidar.py + bvh.py).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Tuple


# ────────────────────────────────────────────────────────────────────────────
# Pattern config + standard pattern generators
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class SinglePatternCfg:
    """Single-ray pattern (one ray straight in `direction`)."""
    direction: tuple = (0.0, 0.0, -1.0)


@dataclass
class LinePatternCfg:
    """Line of N rays evenly spaced along a sensor-frame axis.

    Useful for forward-looking obstacle bars on wheeled / mobile bases.
    """
    num_rays: int = 16
    axis: tuple = (1.0, 0.0, 0.0)         # axis to spread origins along
    length: float = 1.0                    # total spread length
    direction: tuple = (0.0, 0.0, -1.0)    # ray direction (all parallel)


@dataclass
class GridPatternCfg:
    """2D grid of rays centred on the sensor origin.

    `size = (sx, sy)` is total scan area; `resolution` is cell side length.
    Grid is laid out in the sensor's local x-y plane; all rays point in
    `direction`. Ray count = floor(sx/res + 1) × floor(sy/res + 1).
    """
    resolution: float = 0.1
    size: tuple = (1.0, 1.0)
    direction: tuple = (0.0, 0.0, -1.0)


def single_pattern(cfg: SinglePatternCfg) -> Tuple[List[tuple], List[tuple]]:
    """Returns (origins, directions) in sensor frame.

    `origins` are sensor-frame ray start offsets (here always (0,0,0) for
    single ray), `directions` are sensor-frame unit vectors.
    """
    return [(0.0, 0.0, 0.0)], [_norm3(cfg.direction)]


def line_pattern(cfg: LinePatternCfg) -> Tuple[List[tuple], List[tuple]]:
    """N evenly-spaced rays along `axis`. All directions parallel."""
    n = max(1, cfg.num_rays)
    axis = _norm3(cfg.axis)
    direction = _norm3(cfg.direction)
    half_len = cfg.length * 0.5
    origins: List[tuple] = []
    for i in range(n):
        t = -half_len + cfg.length * (i / (n - 1)) if n > 1 else 0.0
        origins.append((axis[0] * t, axis[1] * t, axis[2] * t))
    directions = [direction] * n
    return origins, directions


def grid_pattern(cfg: GridPatternCfg) -> Tuple[List[tuple], List[tuple]]:
    """2D grid of ray origins on sensor x-y plane, all rays in `direction`."""
    sx, sy = cfg.size
    res = max(1e-6, cfg.resolution)
    direction = _norm3(cfg.direction)
    # Ray count along each axis. round() to nearest int + 1 for inclusive grid.
    nx = max(1, int(round(sx / res)) + 1)
    ny = max(1, int(round(sy / res)) + 1)
    origins: List[tuple] = []
    half_sx = sx * 0.5
    half_sy = sy * 0.5
    for iy in range(ny):
        y = -half_sy + (sy * (iy / (ny - 1)) if ny > 1 else 0.0)
        for ix in range(nx):
            x = -half_sx + (sx * (ix / (nx - 1)) if nx > 1 else 0.0)
            origins.append((x, y, 0.0))
    directions = [direction] * (nx * ny)
    return origins, directions


# ────────────────────────────────────────────────────────────────────────────
# RayCaster config + data
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class _OffsetCfg:
    """Optional rigid offset of the sensor relative to its parent link."""
    pos: tuple = (0.0, 0.0, 0.0)
    # Quaternion (x, y, z, w). Identity by default.
    rot: tuple = (0.0, 0.0, 0.0, 1.0)


@dataclass
class RayCasterCfg:
    """Mirror of isaaclab.sensors.ray_caster.RayCasterCfg."""
    prim_path: str = ""
    # Names of the mesh prims the sensor raycasts against. In our isaacsim
    # primitive scene this is a free-form tag; the actual scene to raycast
    # against is passed to `sample(scene)`.
    mesh_prim_paths: List[str] = field(default_factory=list)
    # When True, only the yaw component of the link orientation rotates the
    # ray frame (canonical for foot-mounted height scans — keeps the scan
    # square to the world regardless of foot roll/pitch).
    attach_yaw_only: bool = True
    offset: _OffsetCfg = field(default_factory=_OffsetCfg)
    pattern_cfg: Any = field(default_factory=SinglePatternCfg)
    # Max distance for finite-range raycasts. None = unlimited.
    max_distance: Optional[float] = None
    # Cached attribute name for the convenience `Cfg` constructor.
    OffsetCfg = _OffsetCfg


@dataclass
class RayCasterData:
    """Mirror of isaaclab.sensors.ray_caster.RayCasterData."""
    # Sensor pose in world frame.
    pos_w: tuple
    quat_w: tuple
    # Per-ray world-frame hit positions. (inf, inf, inf) when ray missed.
    ray_hits_w: List[tuple]
    # Per-ray scalar distance from sensor origin. math.inf when missed.
    ray_distances: List[float]
    # Per-ray index in the scene's primitive array (-1 = no hit).
    ray_prim_indices: List[int]
    # Per-ray sensor-frame origins + directions (handy for debug viz).
    ray_origins_sensor: List[tuple]
    ray_directions_sensor: List[tuple]


# ────────────────────────────────────────────────────────────────────────────
# RayCaster sensor
# ────────────────────────────────────────────────────────────────────────────


class RayCaster:
    """Pattern-based ray-bundle sensor.

    Construction parses `cfg.pattern_cfg` once and caches the sensor-frame
    (origins, directions). `sample()` transforms them into world frame
    given the parent link pose, then dispatches each ray through the
    scene's `nearest_hit`.

    Scene can be either an `isaacsim.sensors.Scene` (linear scan) or
    `isaacsim.sensors.BvhScene` (O(log N) accelerated). The contract
    matches both — `nearest_hit(origin, dir_) -> (t, idx) | None` and
    `.primitives` list.
    """

    def __init__(self, cfg: RayCasterCfg, scene: Any):
        self.cfg = cfg
        self.scene = scene
        # Resolve pattern → cached sensor-frame (origins, directions).
        pat = cfg.pattern_cfg
        if isinstance(pat, SinglePatternCfg):
            origins, dirs = single_pattern(pat)
        elif isinstance(pat, LinePatternCfg):
            origins, dirs = line_pattern(pat)
        elif isinstance(pat, GridPatternCfg):
            origins, dirs = grid_pattern(pat)
        else:
            raise TypeError(
                f"unsupported pattern_cfg type: {type(pat).__name__}; "
                f"expected SinglePatternCfg / LinePatternCfg / GridPatternCfg"
            )
        # Apply rigid offset (pos + rot quat) — pre-bake into sensor frame.
        offset_pos = tuple(cfg.offset.pos)
        offset_rot = tuple(cfg.offset.rot)
        self._origins_sensor: List[tuple] = [
            _add3(offset_pos, _quat_rotate(offset_rot, o)) for o in origins
        ]
        self._directions_sensor: List[tuple] = [
            _quat_rotate(offset_rot, d) for d in dirs
        ]
        self.num_rays = len(self._origins_sensor)

    @property
    def origins_sensor(self) -> List[tuple]:
        return list(self._origins_sensor)

    @property
    def directions_sensor(self) -> List[tuple]:
        return list(self._directions_sensor)

    def update_scene(self, scene: Any) -> None:
        """Swap the scene the sensor raycasts against (sensor frame caches
        are unchanged)."""
        self.scene = scene

    def sample(self, link_pos: tuple, link_quat: tuple,
               time: float = 0.0) -> RayCasterData:
        """Sample the ray bundle against the current scene.

        `link_pos` = world-frame position of the parent link.
        `link_quat` = world-frame orientation as (x, y, z, w) quaternion.
        Returns RayCasterData populated for every ray.
        """
        # Effective sensor orientation: yaw-only when configured.
        sensor_quat = (
            _quat_yaw_only(link_quat) if self.cfg.attach_yaw_only
            else tuple(link_quat)
        )
        sensor_pos = link_pos  # rigid offset already baked into ray origins.

        hits_w: List[tuple] = []
        dists: List[float] = []
        prim_idxs: List[int] = []
        max_d = self.cfg.max_distance

        for o_s, d_s in zip(self._origins_sensor, self._directions_sensor):
            # Transform ray origin + direction into world frame.
            o_world = _add3(sensor_pos, _quat_rotate(sensor_quat, o_s))
            d_world = _quat_rotate(sensor_quat, d_s)
            # Re-normalize defensively.
            d_world = _norm3(d_world)
            hit = self.scene.nearest_hit(o_world, d_world)
            if hit is None:
                hits_w.append((math.inf, math.inf, math.inf))
                dists.append(math.inf)
                prim_idxs.append(-1)
                continue
            t, idx = hit
            if max_d is not None and t > max_d:
                hits_w.append((math.inf, math.inf, math.inf))
                dists.append(math.inf)
                prim_idxs.append(-1)
                continue
            hit_pt = (
                o_world[0] + d_world[0] * t,
                o_world[1] + d_world[1] * t,
                o_world[2] + d_world[2] * t,
            )
            hits_w.append(hit_pt)
            dists.append(t)
            prim_idxs.append(idx)

        return RayCasterData(
            pos_w=tuple(sensor_pos),
            quat_w=tuple(sensor_quat),
            ray_hits_w=hits_w,
            ray_distances=dists,
            ray_prim_indices=prim_idxs,
            ray_origins_sensor=list(self._origins_sensor),
            ray_directions_sensor=list(self._directions_sensor),
        )

    def get_height_scan(self, link_pos: tuple, link_quat: tuple,
                        time: float = 0.0) -> List[float]:
        """Convenience: returns just the per-ray hit-Z (height) values.

        Common usage in legged locomotion: the observation is "scan height
        minus foot height" — a flat surface gives all zeros, a step or
        slope gives the relative elevation. When `attach_yaw_only=True`
        (the default), the scan stays square to world even as the foot
        rolls/pitches with the gait.
        """
        data = self.sample(link_pos, link_quat, time)
        return [hit[2] if math.isfinite(hit[2]) else math.inf
                for hit in data.ray_hits_w]


# ────────────────────────────────────────────────────────────────────────────
# Quaternion + 3-vec helpers (stdlib-only)
# ────────────────────────────────────────────────────────────────────────────


def _norm3(v: tuple) -> tuple:
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if n < 1e-12:
        return (0.0, 0.0, 0.0)
    return (v[0] / n, v[1] / n, v[2] / n)


def _add3(a: tuple, b: tuple) -> tuple:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _quat_rotate(q: tuple, v: tuple) -> tuple:
    """Rotate 3-vec by quaternion (x, y, z, w). v' = q v q^-1."""
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


def _quat_yaw_only(q: tuple) -> tuple:
    """Extract the yaw component of `q` and return it as a yaw-only
    quaternion. Useful for foot-mounted scans that should stay world-axis
    aligned regardless of roll/pitch.

    Yaw axis = world +z. For a quaternion (x, y, z, w):
        yaw = atan2(2(wz + xy), 1 - 2(y² + z²))
    The yaw-only quaternion is then (0, 0, sin(yaw/2), cos(yaw/2)).
    """
    qx, qy, qz, qw = q
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    half = yaw * 0.5
    return (0.0, 0.0, math.sin(half), math.cos(half))
