"""omni.isaac — Isaac Sim core utilities namespace.

R1.x scope: cloner (GridCloner parallel scene instantiation).
Future: motion_generation (already provided at isaacsim.motion_generation),
range_sensor, sensor, gym, utils, universal_robots, franka, wheeled_robots.
"""

from . import cloner

__all__ = ["cloner"]
