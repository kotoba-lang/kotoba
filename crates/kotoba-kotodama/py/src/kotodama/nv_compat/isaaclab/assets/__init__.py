"""isaaclab.assets — declarative scene asset wrappers.

Mirror of `isaaclab.assets` (Isaac Lab 1.x). The canonical Isaac Lab asset
abstraction. Bridges the iter 42 spawners (`isaaclab.sim.spawners`) and
the env physics buffers (DirectRLEnv / ManagerBasedRLEnv) by wrapping:

  - prim_path (USD path)
  - spawn cfg (UsdFileCfg / shape cfg from spawners)
  - initial state cfg (pose + joint_pos + joint_vel)
  - stateful read/write buffers (joint state, root pose)

Three asset classes mirroring upstream:

  - AssetBaseCfg / AssetBase
        Common base; holds prim_path + spawn cfg + initial pose.
  - RigidObjectCfg / RigidObject
        Single-body rigid prim. Tracks root_pose + root_velocity.
  - ArticulationCfg / Articulation
        Multi-link articulated robot. Wraps an `ArticulatedSystem` from
        the kernel + stateful joint_pos / joint_vel / joint_effort buffers
        + initial-state reset.

Standard usage (matches Isaac Lab patterns):

    cartpole_cfg = ArticulationCfg(
        prim_path="/World/cartpole",
        spawn=UsdFileCfg(urdf_text=URDF_TEXT),
        init_state=ArticulationInitialStateCfg(
            pos=(0.0, 0.0, 0.0),
            joint_pos={"slider_to_cart": 0.0, "cart_to_pole": 0.05},
        ),
    )
    cartpole = Articulation(cartpole_cfg)
    cartpole.write_root_pose_to_sim()             # spawns prim onto registry
    cartpole.reset()                              # arm joint state to init_state

    # Per-step read/write:
    cartpole.update(physics_dt=1/120)             # advance internal state
    pos = cartpole.data.joint_pos                 # current joint positions
    cartpole.set_joint_position_target([0.0, 0.1])
"""

from .articulation import (
    Articulation,
    ArticulationCfg,
    ArticulationData,
    ArticulationInitialStateCfg,
)
from .asset_base import AssetBase, AssetBaseCfg, AssetBaseInitialStateCfg
from .rigid_object import (
    RigidObject,
    RigidObjectCfg,
    RigidObjectData,
    RigidObjectInitialStateCfg,
)

__all__ = [
    "AssetBaseCfg", "AssetBase", "AssetBaseInitialStateCfg",
    "RigidObjectCfg", "RigidObject", "RigidObjectData", "RigidObjectInitialStateCfg",
    "ArticulationCfg", "Articulation", "ArticulationData",
    "ArticulationInitialStateCfg",
]
