"""isaaclab.sensors — high-level RL sensor wrappers (heightfield raycasters, …).

Distinct from `isaacsim.sensors` (low-level Camera / Lidar / IMU / ContactSensor):
this namespace provides Isaac Lab's higher-level sensors that compose on
top of the low-level primitives. Today:

  - RayCaster — pattern-based ray bundle (foot-mounted height scan for
    legged locomotion, body-mounted obstacle scan for navigation). Built
    on `isaacsim.sensors.BvhScene` for O(log N) intersection.

Future R1.x adds:
  - RayCasterCamera (depth-from-rays compositor)
  - FrameTransformer (relative-pose sensor between two links)
  - ContactSensorIMU (combined contact + IMU at a specific link)
"""

from .ray_caster import (
    GridPatternCfg,
    LinePatternCfg,
    RayCaster,
    RayCasterCfg,
    RayCasterData,
    SinglePatternCfg,
    grid_pattern,
    line_pattern,
    single_pattern,
)

__all__ = [
    "RayCaster", "RayCasterCfg", "RayCasterData",
    "GridPatternCfg", "LinePatternCfg", "SinglePatternCfg",
    "grid_pattern", "line_pattern", "single_pattern",
]
