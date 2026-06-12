"""ANYmal C asset wrapper — 12-DoF quadruped (4 legs × 3 joints).

Mirrors the upstream pattern `isaacsim.assets.AnymalC(prim_path=...)`.

Specs sourced from the publicly-distributed ANYbotics ANYmal C URDF
(github.com/ANYbotics/anymal_c_simple_description, BSD-3) and academic
locomotion papers (Hwangbo et al. 2019 "Learning Agile and Dynamic
Motor Skills for Legged Robots"). No proprietary content (no mesh
references, no NVIDIA Isaac Sim USD references); the URDF is a
minimal kinematic-tree reproduction so the wrapper is self-contained
and substrate-publishable.

Trademark: "ANYmal" is a trademark of ANYbotics AG; this wrapper is
API namespace localization only (matching the public ROS URDF spec —
Google v. Oracle 2021 API fair use).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

from .urdf_builder import build_branched_urdf


# Per-leg joint specs. ANYmal C has 3 actuated joints per leg (HAA / HFE /
# KFE) with effort limits around 80 N·m and velocity limits around 7.5 rad/s
# per ANYbotics public docs. Joint limits are roughly ±π but joint-specific.
_LEG_NAMES = ("LF", "LH", "RF", "RH")  # Left Front, Left Hind, Right Front, Right Hind

# (joint_suffix, axis_xyz, lower, upper, vel_limit, effort_limit)
_LEG_JOINTS = (
    ("HAA", (1.0, 0.0, 0.0), -0.611, 0.611, 7.5, 80.0),   # hip ab/adduction (roll)
    ("HFE", (0.0, 1.0, 0.0), -9.42, 9.42, 7.5, 80.0),    # hip flex/extension (pitch)
    ("KFE", (0.0, 1.0, 0.0), -9.42, 9.42, 7.5, 80.0),    # knee flex/extension
)


def _build_anymal_urdf() -> str:
    """Build a self-contained URDF for ANYmal C: base + 4 branched legs.

    Checks for a vendored URDF at
    70-tools/e7m-sim/scenes/anymal_c/anymal_c.urdf first; falls back to
    a programmatic minimal version (no meshes / no visuals).
    """
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        candidate = ancestor / "70-tools" / "e7m-sim" / "scenes" / "anymal_c" / "anymal_c.urdf"
        if candidate.exists():
            return candidate.read_text()
    # Programmatic fallback.
    branches = []
    branch_link_prefixes = []
    for leg in _LEG_NAMES:
        leg_joints = []
        for suffix, axis, lower, upper, vel, effort in _LEG_JOINTS:
            leg_joints.append(
                {
                    "name": f"{leg}_{suffix}",
                    "type": "revolute",
                    "axis": axis,
                    "lower": lower,
                    "upper": upper,
                    "velocity": vel,
                    "effort": effort,
                    "origin_xyz": (0.0, 0.0, -0.15),  # downward
                }
            )
        branches.append(leg_joints)
        branch_link_prefixes.append(f"{leg}_link")
    return build_branched_urdf(
        robot_name="anymal_c",
        base_link="base",
        branches=branches,
        branch_link_prefixes=branch_link_prefixes,
    )


# Standing pose: HAA=0 (legs vertical), HFE=±0.4 (front +, hind −), KFE=∓0.8.
# Convention: front legs flex forward; hind legs flex backward.
_STANDING_POSE: Tuple[float, ...] = (
    0.0,  0.4, -0.8,   # LF_HAA, LF_HFE, LF_KFE
    0.0, -0.4,  0.8,   # LH_HAA, LH_HFE, LH_KFE
    0.0,  0.4, -0.8,   # RF_HAA, RF_HFE, RF_KFE
    0.0, -0.4,  0.8,   # RH_HAA, RH_HFE, RH_KFE
)


def _make_joint_names() -> Tuple[str, ...]:
    """Materialise 12 joint names in canonical order
    (LF first, then LH, RF, RH; HAA→HFE→KFE within each leg)."""
    names: list = []
    for leg in _LEG_NAMES:
        for suffix, *_ in _LEG_JOINTS:
            names.append(f"{leg}_{suffix}")
    return tuple(names)


_JOINT_NAMES = _make_joint_names()


@dataclass
class AnymalC:
    """Pre-configured ANYmal C quadruped asset.

    Auto-builds a self-contained branched URDF (or loads a vendored one
    from 70-tools/e7m-sim/scenes/anymal_c/anymal_c.urdf when available).
    12 DoF total — 4 legs × (HAA + HFE + KFE).

    Pairs directly with:
      - iter 60 ObservationManager standard locomotion observations
        (base_lin_vel_b / base_ang_vel_b / projected_gravity /
        joint_pos_rel_default / last_action / height_scan)
      - iter 61 standard locomotion rewards (track_lin_vel_xy_exp /
        track_ang_vel_z_exp / lin_vel_z_l2 / ang_vel_xy_l2 /
        feet_air_time / dof_torques_l2 / alive_bonus)
      - iter 62 domain-randomization events (push_by_setting_velocity /
        randomize_friction / randomize_com / randomize_mass)
      - iter 58 terrain_levels_vy curriculum

    Construction example:
        from kotodama.nv_compat.isaacsim.assets import AnymalC
        from kotodama.nv_compat.isaacsim.core.api import World, Articulation

        anymal = AnymalC(prim_path="/World/Anymal_0")
        w = World()
        art = Articulation(prim_path=anymal.prim_path, name=anymal.name,
                            urdf_text=anymal.urdf_text)
        w.add_articulation(art)
        art.set_joint_positions(anymal.default_joint_positions)
    """
    prim_path: str = "/World/Anymal"
    name: str = "anymal_c"
    urdf_text: str = field(default_factory=_build_anymal_urdf)

    joint_names: Tuple[str, ...] = _JOINT_NAMES
    dof_count: int = 12

    # Canonical standing pose (front legs flex forward, hind legs back).
    default_joint_positions: Tuple[float, ...] = _STANDING_POSE
    default_joint_velocities: Tuple[float, ...] = (0.0,) * 12

    # Per-joint limits (matched to URDF spec above).
    joint_lower_limits: Tuple[float, ...] = (
        -0.611, -9.42, -9.42,    # LF
        -0.611, -9.42, -9.42,    # LH
        -0.611, -9.42, -9.42,    # RF
        -0.611, -9.42, -9.42,    # RH
    )
    joint_upper_limits: Tuple[float, ...] = (
         0.611,  9.42,  9.42,    # LF
         0.611,  9.42,  9.42,    # LH
         0.611,  9.42,  9.42,    # RF
         0.611,  9.42,  9.42,    # RH
    )
    joint_velocity_limits: Tuple[float, ...] = (7.5,) * 12
    effort_limits: Tuple[float, ...] = (80.0,) * 12

    # Foot link names (for contact / air-time observations + rewards).
    foot_link_names: Tuple[str, ...] = (
        "LF_foot", "LH_foot", "RF_foot", "RH_foot",
    )
    base_link_name: str = "base"

    # Leg layout helpers.
    leg_names: Tuple[str, ...] = ("LF", "LH", "RF", "RH")
    joints_per_leg: int = 3

    def leg_indices(self, leg: str) -> Tuple[int, int, int]:
        """Indices into joint_names for a given leg ('LF' / 'LH' / 'RF' / 'RH')."""
        if leg not in self.leg_names:
            raise ValueError(
                f"AnymalC.leg_indices: leg must be one of {self.leg_names}; got {leg!r}"
            )
        leg_idx = self.leg_names.index(leg)
        start = leg_idx * self.joints_per_leg
        return (start, start + 1, start + 2)

    def haa_indices(self) -> Tuple[int, ...]:
        """Indices of all HAA (hip abduction) joints."""
        return tuple(i for i, n in enumerate(self.joint_names) if n.endswith("_HAA"))

    def hfe_indices(self) -> Tuple[int, ...]:
        """Indices of all HFE (hip flex/extension) joints."""
        return tuple(i for i, n in enumerate(self.joint_names) if n.endswith("_HFE"))

    def kfe_indices(self) -> Tuple[int, ...]:
        """Indices of all KFE (knee flex/extension) joints."""
        return tuple(i for i, n in enumerate(self.joint_names) if n.endswith("_KFE"))
