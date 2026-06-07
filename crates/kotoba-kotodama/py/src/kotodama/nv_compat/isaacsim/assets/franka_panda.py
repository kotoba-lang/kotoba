"""Franka Emika Panda asset wrapper — 7-DoF arm + 2-finger gripper (9 DoF).

Mirrors the upstream pattern `isaacsim.assets.Franka(prim_path=...)`.

Specs sourced from the public Franka Robotics FCI documentation
(https://frankarobotics.github.io/docs/control_parameters.html — joint
ranges, velocity limits, effort limits) and the publicly-distributed
Franka URDF (github.com/frankaemika/franka_ros, Apache 2.0). No
proprietary content (no mesh references, no NVIDIA Isaac Sim USD
references); the URDF is a minimal kinematic-chain reproduction with
unit-mass placeholder inertias so the wrapper is self-contained and
substrate-publishable.

Trademark: "Franka Emika" and "Panda" are trademarks of Franka Robotics
GmbH; this wrapper is API namespace localization only (matching the
public FCI spec — Google v. Oracle 2021 API fair use).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple

from .urdf_builder import build_serial_chain_urdf


# Joint specs (Franka FCI public documentation):
#   ±2.8973 rad / ±2.1750 rad/s / ±87 N·m for joints 1-4
#   ±2.8973 rad (asymmetric for J4, J6) / ±2.6100 rad/s / ±12 N·m for joints 5-7
_PANDA_ARM_JOINTS: Tuple[Tuple[str, float, float, float, float, float, float], ...] = (
    # (name, lower, upper, vel_limit, effort_limit, axis_x, axis_z)
    ("panda_joint1", -2.8973,  2.8973, 2.1750, 87.0, 0.0, 1.0),
    ("panda_joint2", -1.7628,  1.7628, 2.1750, 87.0, 0.0, 1.0),
    ("panda_joint3", -2.8973,  2.8973, 2.1750, 87.0, 0.0, 1.0),
    ("panda_joint4", -3.0718, -0.0698, 2.1750, 87.0, 0.0, 1.0),
    ("panda_joint5", -2.8973,  2.8973, 2.6100, 12.0, 0.0, 1.0),
    ("panda_joint6", -0.0175,  3.7525, 2.6100, 12.0, 0.0, 1.0),
    ("panda_joint7", -2.8973,  2.8973, 2.6100, 12.0, 0.0, 1.0),
)

# Gripper finger joints (parallel jaw; range 0..0.04 m linear).
_PANDA_FINGER_JOINTS: Tuple[Tuple[str, float, float, float, float], ...] = (
    # (name, lower, upper, vel_limit, effort_limit) — prismatic joints
    ("panda_finger_joint1", 0.0, 0.04, 0.2, 20.0),
    ("panda_finger_joint2", 0.0, 0.04, 0.2, 20.0),
)


def _build_franka_urdf() -> str:
    """Build a self-contained kinematic-chain URDF for the 7-DoF Franka arm
    + 2-finger gripper. No mesh refs; placeholder unit-mass inertias.

    For full visual / collision meshes use a vendored
    `70-tools/e7m-sim/scenes/franka/franka.urdf` (Apache 2.0 from
    github.com/frankaemika/franka_ros) loaded at runtime by the substrate.
    """
    # First check if a vendored URDF exists on disk (preferred path).
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        candidate = ancestor / "70-tools" / "e7m-sim" / "scenes" / "franka" / "franka.urdf"
        if candidate.exists():
            return candidate.read_text()
    # Fall back to a programmatic minimal URDF.
    joints = []
    for name, lower, upper, vel, effort, ax, az in _PANDA_ARM_JOINTS:
        joints.append(
            {
                "name": name,
                "type": "revolute",
                "axis": (ax, 0.0, az),
                "lower": lower,
                "upper": upper,
                "velocity": vel,
                "effort": effort,
                "origin_xyz": (0.0, 0.0, 0.1),
            }
        )
    for name, lower, upper, vel, effort in _PANDA_FINGER_JOINTS:
        joints.append(
            {
                "name": name,
                "type": "prismatic",
                "axis": (0.0, 1.0, 0.0),
                "lower": lower,
                "upper": upper,
                "velocity": vel,
                "effort": effort,
                "origin_xyz": (0.0, 0.0, 0.05),
            }
        )
    return build_serial_chain_urdf("panda", joints)


@dataclass
class FrankaPanda:
    """Pre-configured Franka Emika Panda asset.

    Auto-builds a self-contained URDF (or loads a vendored one from
    70-tools/e7m-sim/scenes/franka/franka.urdf when available). Exposes
    joint names, default pose, full joint/effort/velocity limits.

    Pairs directly with:
      - iter 41 DifferentialIKController (arm 7-DoF)
      - iter 63 OperationalSpaceController (arm 7-DoF)
      - iter 64 DifferentialInverseKinematicsAction (arm)
      - iter 65 BinaryJointPositionAction (gripper) — open_command=
        gripper_open_pose, close_command=gripper_close_pose

    Construction example:
        from kotodama.nv_compat.isaacsim.assets import FrankaPanda
        from kotodama.nv_compat.isaacsim.core.api import World, Articulation

        franka = FrankaPanda(prim_path="/World/Franka_0")
        w = World()
        art = Articulation(prim_path=franka.prim_path, name=franka.name,
                            urdf_text=franka.urdf_text)
        w.add_articulation(art)
        art.set_joint_positions(franka.default_joint_positions)
    """
    prim_path: str = "/World/Franka"
    name: str = "franka_panda"
    urdf_text: str = field(default_factory=_build_franka_urdf)

    # 9-DoF: 7 arm + 2 finger
    joint_names: Tuple[str, ...] = (
        "panda_joint1", "panda_joint2", "panda_joint3", "panda_joint4",
        "panda_joint5", "panda_joint6", "panda_joint7",
        "panda_finger_joint1", "panda_finger_joint2",
    )
    arm_joint_names: Tuple[str, ...] = (
        "panda_joint1", "panda_joint2", "panda_joint3", "panda_joint4",
        "panda_joint5", "panda_joint6", "panda_joint7",
    )
    finger_joint_names: Tuple[str, ...] = (
        "panda_finger_joint1", "panda_finger_joint2",
    )
    dof_count: int = 9
    arm_dof_count: int = 7
    finger_dof_count: int = 2

    # Standard Franka "home" pose (arm) + open gripper.
    default_joint_positions: Tuple[float, ...] = (
        0.0, -0.7854, 0.0, -2.3562, 0.0, 1.5708, 0.7854,    # arm home
        0.04, 0.04,                                          # gripper open
    )
    default_joint_velocities: Tuple[float, ...] = (0.0,) * 9

    # Per-joint limits (from FCI public spec).
    joint_lower_limits: Tuple[float, ...] = (
        -2.8973, -1.7628, -2.8973, -3.0718, -2.8973, -0.0175, -2.8973,
         0.0,     0.0,
    )
    joint_upper_limits: Tuple[float, ...] = (
         2.8973,  1.7628,  2.8973, -0.0698,  2.8973,  3.7525,  2.8973,
         0.04,    0.04,
    )
    joint_velocity_limits: Tuple[float, ...] = (
         2.1750,  2.1750,  2.1750,  2.1750,  2.6100,  2.6100,  2.6100,
         0.2,     0.2,
    )
    effort_limits: Tuple[float, ...] = (
         87.0,    87.0,    87.0,    87.0,    12.0,    12.0,    12.0,
         20.0,    20.0,
    )

    # Gripper command convenience.
    gripper_open_command: Tuple[float, float] = (0.04, 0.04)
    gripper_close_command: Tuple[float, float] = (0.0, 0.0)

    # EE link name (for Jacobian providers).
    ee_link_name: str = "panda_hand"

    def home_pose(self) -> Tuple[float, ...]:
        """Returns the canonical Franka 'home' (ready-to-pick) joint pose
        + open gripper. Same as default_joint_positions but explicit."""
        return self.default_joint_positions

    def arm_indices(self) -> Tuple[int, ...]:
        """Indices into joint_names for the 7 arm joints (0..6)."""
        return tuple(range(7))

    def finger_indices(self) -> Tuple[int, ...]:
        """Indices into joint_names for the 2 finger joints (7..8)."""
        return (7, 8)
