"""isaacsim.assets — pre-configured robot asset wrappers.

Mirrors `isaacsim.assets` (Isaac Sim 4.x) for the robots that the kami
substrate can simulate today. Each wrapper bundles:
  - URDF text (loaded from 70-tools/e7m-sim/scenes/<robot>/<robot>.urdf)
  - Default joint positions (rest pose)
  - DOF metadata (joint names, count, limits)
  - Optional default sensor mounts (cameras, IMUs)

Standard upstream Isaac Sim asset names (Franka, UR10, ANYmal, Cassie,
Carter, Jetbot) require their respective URDFs which aren't yet vendored
into religious-corp substrate. The R1.x asset surface starts with the
substrate-native robots (Cartpole, DoublePendulum, PlanarChain) and grows
as more URDFs land.
"""

from .anymal_c import AnymalC
from .cartpole import Cartpole
from .double_pendulum import DoublePendulum
from .franka_panda import FrankaPanda
from .planar_chain import PlanarChain
from .urdf_builder import (
    build_branched_urdf,
    build_serial_chain_urdf,
    count_joints,
    joint_names,
)

__all__ = [
    # Original substrate-native robots
    "Cartpole", "DoublePendulum", "PlanarChain",
    # Canonical Isaac Lab benchmarks (iter 67)
    "FrankaPanda", "AnymalC",
    # URDF construction helpers
    "build_serial_chain_urdf", "build_branched_urdf",
    "count_joints", "joint_names",
]
