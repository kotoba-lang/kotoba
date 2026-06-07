"""InteractiveScene + cfg — composition of terrain + assets + sensors + cloner.

Mirrors `isaaclab.scene.InteractiveScene` (Isaac Lab 1.x). The scene is a
declarative container: instantiate with a cfg, then call update(world) each
step to refresh sensor data against current env state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class LinkState:
    """Per-env link kinematics passed to sensors via the link-state callback.

    Position / linear-velocity / angular-velocity are in world frame.
    Orientation is a (x, y, z, w) quaternion (glam Quat layout, matches IMU
    expectations).
    """
    position: tuple = (0.0, 0.0, 0.0)
    linear_velocity: tuple = (0.0, 0.0, 0.0)
    angular_velocity: tuple = (0.0, 0.0, 0.0)
    orientation: tuple = (0.0, 0.0, 0.0, 1.0)


@dataclass
class SensorMount:
    """Per-env sensor attachment.

    `sensor_factory(env_idx)` returns a fresh sensor instance for env_idx.
    `link_name` names the articulation link the sensor is rigidly attached to.
    """
    sensor_factory: Any  # callable: env_idx -> sensor (Camera / Lidar / Imu / ContactSensor)
    link_name: str = "base"


@dataclass
class InteractiveSceneCfg:
    """Declarative scene config.

    All fields are optional; an empty scene is valid (useful for unit tests).
    """
    num_envs: int = 1
    env_spacing: float = 4.0
    # Robot asset (Cartpole / DoublePendulum / PlanarChain / ...). Each env
    # gets its own articulation instance with the asset's URDF + defaults.
    robot: Any = None
    # Terrain HeightField (from isaaclab.terrains).
    terrain: Any = None
    # Cloner instance (typically a GridCloner). If None, a default GridCloner
    # with cfg.env_spacing is constructed.
    cloner: Any = None
    # Named sensor mounts; each materialized per env.
    sensors: Dict[str, SensorMount] = field(default_factory=dict)
    # Optional named "props" — additional asset entries (e.g. cubes, walls).
    props: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InteractiveScene:
    """Materializes an InteractiveSceneCfg into per-env asset / sensor instances.

    After construction:
      - .articulations[env_idx]  — list of N articulation instances (or empty)
      - .sensors[name][env_idx]  — sensor instances per env, per mount name
      - .env_positions[env_idx]  — world-frame (x, y, z) per env
      - .terrain                  — bound HeightField (or None)

    Call `scene.update(time)` each physics step to refresh sensor data. The
    refreshed readings are cached on `_latest_observations[env_idx][sensor_name]`
    and retrievable via `get_latest_observation` / `get_latest_observations`.

    Sensor sampling requires two providers:
      - `set_link_state_provider(fn)` where fn(env_idx, link_name) -> LinkState | None
      - `set_lidar_scene(scene)` for Lidar/Contact ray + distance tests
    Without these, `update()` is a graceful no-op for the relevant sensor type.
    """
    cfg: InteractiveSceneCfg
    articulations: List[Any] = field(default_factory=list)
    sensors: Dict[str, List[Any]] = field(default_factory=dict)
    env_positions: List[tuple] = field(default_factory=list)
    terrain: Any = None

    def __post_init__(self):
        # Resolve cloner (default to GridCloner if none).
        cloner = self.cfg.cloner
        if cloner is None:
            from ...omni.isaac.cloner import GridCloner
            cloner = GridCloner(spacing=self.cfg.env_spacing)
        self._cloner = cloner

        # Compute per-env world positions.
        self.env_positions = cloner.positions_for_envs(self.cfg.num_envs)

        # Materialize articulations. Real instantiation happens when caller
        # wires articulations into a World; here we just store the asset
        # reference so subsequent code can spawn from it.
        self.articulations = [self.cfg.robot] * self.cfg.num_envs if self.cfg.robot else []

        # Materialize sensors per env.
        self.sensors = {}
        for name, mount in self.cfg.sensors.items():
            self.sensors[name] = [mount.sensor_factory(i) for i in range(self.cfg.num_envs)]

        # Bind terrain (no copy; one terrain shared across envs by default).
        self.terrain = self.cfg.terrain

        # Auto-sample state.
        self._link_state_fn: Optional[Callable[[int, str], Optional[LinkState]]] = None
        self._lidar_scene: Any = None
        self._latest_observations: List[Dict[str, Any]] = [
            {} for _ in range(self.cfg.num_envs)
        ]
        self._last_update_time: float = 0.0

    @property
    def num_envs(self) -> int:
        return self.cfg.num_envs

    def position_for_env(self, env_idx: int) -> tuple:
        """World-frame (x, y, z) for the named env."""
        return self.env_positions[env_idx]

    def get_sensor(self, name: str, env_idx: int) -> Any:
        """Specific sensor instance for (name, env_idx)."""
        return self.sensors[name][env_idx]

    # ----- auto-sample wiring -----

    def set_link_state_provider(
        self, fn: Callable[[int, str], Optional[LinkState]]
    ) -> None:
        """Install the (env_idx, link_name) -> LinkState callback used by
        `update()` to sample IMU / contact / camera / lidar mount transforms.
        """
        self._link_state_fn = fn

    def set_lidar_scene(self, scene: Any) -> None:
        """Install the `nv_compat.isaacsim.sensors.Scene` (lidar primitive set)
        used by `update()` to acquire Lidar returns and ContactSensor readings.
        """
        self._lidar_scene = scene

    def get_latest_observation(self, env_idx: int, sensor_name: str) -> Any:
        """Most recent reading for (env_idx, sensor_name), or None if not yet
        sampled."""
        return self._latest_observations[env_idx].get(sensor_name)

    def get_latest_observations(self, env_idx: int) -> Dict[str, Any]:
        """Most recent readings for env_idx — a dict {sensor_name: reading}."""
        return dict(self._latest_observations[env_idx])

    # ----- per-step refresh -----

    def update(self, time: float = 0.0, world: Any = None) -> None:
        """Refresh sensor data for every (sensor_name, env_idx) pair.

        For each sensor mount:
          - Camera  → requires link_state; sets look_at view at (link_position +
                      env_offset) aimed at link +x; cached reading is the
                      resulting 3x4 world→camera affine
          - Lidar   → requires `_lidar_scene`; if link_state given, retargets
                      view at link world position; cached reading is the
                      list[LidarReturn]
          - Imu     → requires link_state; sample(lin_vel, ang_vel, orient, time)
          - Contact → requires `_lidar_scene` + link_state; sample(link_position,
                      scene, time)

        Sensors with unmet requirements are skipped (no cached reading), so
        partial-environment scenes (e.g. lidar-only, no contact scene) still
        run cleanly.

        Sensors are detected by class name (`Camera` / `Lidar` / `Imu` /
        `ContactSensor`) — this avoids importing the sensor modules at scene
        creation time and lets future sensor types plug in without touching
        this file.

        Per-env world offset (`env_positions[env_idx]`) is added to the link
        position so sensors sample in the correct world frame for parallel
        envs cloned at distinct grid cells.

        `world` is currently unused; reserved for future hooks (e.g. broadcasting
        global lighting / time-of-day to sensors).
        """
        self._last_update_time = time

        for name, mount in self.cfg.sensors.items():
            instances = self.sensors[name]
            for env_idx in range(self.cfg.num_envs):
                sensor = instances[env_idx]
                link_state = (
                    self._link_state_fn(env_idx, mount.link_name)
                    if self._link_state_fn is not None
                    else None
                )

                reading = self._sample_one(sensor, link_state, env_idx, time)
                if reading is not None:
                    self._latest_observations[env_idx][name] = reading

    def _sample_one(
        self,
        sensor: Any,
        link_state: Optional[LinkState],
        env_idx: int,
        time: float,
    ) -> Any:
        """Dispatch a single (sensor, env_idx) pair to the right sample method.

        Returns the reading (or None if sampling is not yet possible — e.g.
        Lidar without `_lidar_scene` set).
        """
        cls = type(sensor).__name__
        env_offset = self.env_positions[env_idx]

        if cls == "Camera":
            # Camera: orient look-at from link_state and cache the resulting
            # 3x4 view affine as the "reading" — downstream code can call
            # `Camera.render_points_to_depth_image(points)` against world
            # points it already has. Without link_state we skip; the camera's
            # existing view is unchanged.
            if link_state is None or not hasattr(sensor, "look_at"):
                return None
            eye = (
                link_state.position[0] + env_offset[0],
                link_state.position[1] + env_offset[1],
                link_state.position[2] + env_offset[2],
            )
            # Aim 1 m forward in link +x. Without orientation rotation
            # this is body-frame +x at link origin — adequate for the
            # common chassis-mounted forward-facing camera.
            target = (eye[0] + 1.0, eye[1], eye[2])
            sensor.look_at(eye, target, up=(0.0, 0.0, 1.0))
            return list(sensor.view)

        if cls == "Lidar":
            if self._lidar_scene is None:
                return None
            if link_state is not None:
                # Set view so the lidar origin (sensor frame origin) lands at
                # the link world position + env offset. Identity rotation.
                p = link_state.position
                sensor.view = [
                    1.0, 0.0, 0.0, -(p[0] + env_offset[0]),
                    0.0, 1.0, 0.0, -(p[1] + env_offset[1]),
                    0.0, 0.0, 1.0, -(p[2] + env_offset[2]),
                ]
            return sensor.acquire_data(self._lidar_scene)

        if cls == "Imu":
            if link_state is None:
                return None
            return sensor.sample(
                link_state.linear_velocity,
                link_state.angular_velocity,
                link_state.orientation,
                time,
            )

        if cls == "ContactSensor":
            if self._lidar_scene is None or link_state is None:
                return None
            world_pos = (
                link_state.position[0] + env_offset[0],
                link_state.position[1] + env_offset[1],
                link_state.position[2] + env_offset[2],
            )
            return sensor.sample(world_pos, self._lidar_scene, time)

        return None

    def get_terrain_height(self, world_x: float, world_y: float) -> Optional[float]:
        """Sample terrain elevation at a world-frame point (or None if no
        terrain bound). Assumes terrain is centred at origin."""
        if self.terrain is None:
            return None
        # Convert world position to cell index (terrain is centred at origin).
        cell_size = self.terrain.cell_size
        rows = self.terrain.rows
        cols = self.terrain.cols
        col_f = (world_x / cell_size) + (cols - 1) * 0.5
        row_f = (world_y / cell_size) + (rows - 1) * 0.5
        col = max(0, min(cols - 1, int(round(col_f))))
        row = max(0, min(rows - 1, int(round(row_f))))
        return self.terrain.height_at(row, col)
