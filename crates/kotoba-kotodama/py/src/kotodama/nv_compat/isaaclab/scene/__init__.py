"""isaaclab.scene — Interactive scene composition (terrain + robots + sensors + cloner).

Mirrors `isaaclab.scene` (Isaac Lab 1.x). InteractiveScene is the canonical
container that stitches together all the building blocks built in earlier
iterations into a single declarative scene object:

  - terrain     (iter 21: HeightField)
  - robots      (iter 25: Cartpole / DoublePendulum / PlanarChain assets)
  - sensors     (iter 4-6: Camera / Lidar / IMU / Contact)
  - cloner      (iter 20: GridCloner — per-env world positions)
  - num_envs    (iter 14: N parallel envs)

Standard usage:

    cfg = InteractiveSceneCfg(
        num_envs=1024,
        robot=Cartpole(),
        terrain=flat_terrain(rows=128, cols=128, cell_size=0.1),
        cloner=GridCloner(spacing=4.0),
        sensors={"camera": Camera(...)},
    )
    scene = InteractiveScene(cfg)
    scene.update(world)  # refresh sensor data each step
"""

from .interactive_scene import (
    InteractiveScene,
    InteractiveSceneCfg,
    LinkState,
    SensorMount,
)

__all__ = ["InteractiveScene", "InteractiveSceneCfg", "LinkState", "SensorMount"]
