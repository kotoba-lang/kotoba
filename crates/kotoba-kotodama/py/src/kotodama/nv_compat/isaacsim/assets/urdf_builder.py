"""URDF builder helpers — programmatically construct minimal URDFs from
joint specifications.

Used by the Franka Panda + ANYmal C wrappers when a vendored mesh-bearing
URDF isn't available on disk. Generates valid URDFs (parseable by the iter
61 R1.1 URDF parser + standard ROS urdfdom/urdf_parser_py) with:

  - serial-chain link structure (link0 → link1 → ... → link_N)
  - revolute / prismatic / continuous joints with axes + limits
  - placeholder unit-mass inertias (no mesh refs; no visual / collision)

Branched chains (e.g. quadruped legs all rooted at a single base) are
supported via `build_branched_urdf` which takes a tree of joint dicts.

stdlib-only (xml.etree.ElementTree).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ── inertia placeholder ────────────────────────────────────────────────────


def _unit_inertia() -> str:
    """Standard unit-mass placeholder inertial block (string form)."""
    return (
        '<inertial>'
        '<mass value="1.0"/>'
        '<inertia ixx="0.1" ixy="0" ixz="0" iyy="0.1" iyz="0" izz="0.1"/>'
        '</inertial>'
    )


def _origin_xml(xyz: Sequence[float] = (0.0, 0.0, 0.0),
                 rpy: Sequence[float] = (0.0, 0.0, 0.0)) -> str:
    """`<origin xyz="x y z" rpy="r p y"/>` substring."""
    return (
        f'<origin xyz="{xyz[0]} {xyz[1]} {xyz[2]}" '
        f'rpy="{rpy[0]} {rpy[1]} {rpy[2]}"/>'
    )


def _link_xml(name: str) -> str:
    """A `<link>` element with placeholder inertia (no mesh / visual)."""
    return f'<link name="{name}">{_unit_inertia()}</link>'


def _joint_xml(joint: Dict[str, Any], parent_link: str, child_link: str) -> str:
    """A `<joint>` element from a joint dict.

    Supported keys:
      name        — required
      type        — revolute / prismatic / continuous / fixed (required)
      axis        — (x, y, z) tuple; default (0, 0, 1)
      lower/upper — joint limits (revolute / prismatic only)
      velocity    — velocity limit (revolute / prismatic only)
      effort      — effort limit (revolute / prismatic only)
      origin_xyz  — (x, y, z) tuple; default (0, 0, 0.1)
      origin_rpy  — (r, p, y) tuple; default (0, 0, 0)
    """
    name = joint["name"]
    jtype = joint.get("type", "revolute")
    axis = joint.get("axis", (0.0, 0.0, 1.0))
    origin_xyz = joint.get("origin_xyz", (0.0, 0.0, 0.1))
    origin_rpy = joint.get("origin_rpy", (0.0, 0.0, 0.0))

    parts: List[str] = [
        f'<joint name="{name}" type="{jtype}">',
        _origin_xml(origin_xyz, origin_rpy),
        f'<parent link="{parent_link}"/>',
        f'<child link="{child_link}"/>',
        f'<axis xyz="{axis[0]} {axis[1]} {axis[2]}"/>',
    ]
    if jtype in ("revolute", "prismatic"):
        lower = joint.get("lower", -3.14159)
        upper = joint.get("upper",  3.14159)
        velocity = joint.get("velocity", 1.0)
        effort = joint.get("effort", 100.0)
        parts.append(
            f'<limit lower="{lower}" upper="{upper}" '
            f'velocity="{velocity}" effort="{effort}"/>'
        )
    parts.append('</joint>')
    return ''.join(parts)


# ── public builders ────────────────────────────────────────────────────────


def build_serial_chain_urdf(robot_name: str, joints: List[Dict[str, Any]]) -> str:
    """Build a serial-chain URDF from a list of joint dicts.

    Each joint connects link_i → link_(i+1). Total links = len(joints) + 1.
    Link names follow `<robot_name>_link<i>` (i = 0..len(joints)).

    Args:
        robot_name: name attribute on the <robot> element
        joints:     list of joint dicts (see `_joint_xml` for keys)
    Returns:
        Valid URDF text.
    """
    parts: List[str] = [
        '<?xml version="1.0"?>',
        f'<robot name="{robot_name}">',
    ]
    # Base link.
    parts.append(_link_xml(f"{robot_name}_link0"))
    # Joints + child links.
    for i, joint in enumerate(joints):
        parent = f"{robot_name}_link{i}"
        child = f"{robot_name}_link{i + 1}"
        parts.append(_joint_xml(joint, parent, child))
        parts.append(_link_xml(child))
    parts.append('</robot>')
    return ''.join(parts)


def build_branched_urdf(
    robot_name: str,
    base_link: str,
    branches: List[List[Dict[str, Any]]],
    branch_link_prefixes: Optional[List[str]] = None,
) -> str:
    """Build a URDF with a common base link and multiple serial branches
    (e.g. quadruped — base + 4 legs).

    Args:
        robot_name: name attribute on <robot>
        base_link:  name of the common root link
        branches:   list of per-branch joint-dict lists. Each branch is a
                    serial chain rooted at `base_link`.
        branch_link_prefixes: optional per-branch link prefix (defaults to
                    `branch{i}_link`).
    """
    parts: List[str] = [
        '<?xml version="1.0"?>',
        f'<robot name="{robot_name}">',
        _link_xml(base_link),
    ]
    for b, branch_joints in enumerate(branches):
        prefix = (
            branch_link_prefixes[b]
            if branch_link_prefixes is not None and b < len(branch_link_prefixes)
            else f"branch{b}_link"
        )
        # First joint connects base_link → prefix0.
        first_child = f"{prefix}0"
        parts.append(_joint_xml(branch_joints[0], base_link, first_child))
        parts.append(_link_xml(first_child))
        # Remaining joints chain through the branch.
        for i, joint in enumerate(branch_joints[1:], start=1):
            parent = f"{prefix}{i - 1}"
            child = f"{prefix}{i}"
            parts.append(_joint_xml(joint, parent, child))
            parts.append(_link_xml(child))
    parts.append('</robot>')
    return ''.join(parts)


def count_joints(urdf_text: str) -> int:
    """Count `<joint>` elements in URDF text (excludes type='fixed')."""
    root = ET.fromstring(urdf_text)
    n = 0
    for joint in root.findall("joint"):
        if joint.attrib.get("type") != "fixed":
            n += 1
    return n


def joint_names(urdf_text: str) -> List[str]:
    """Return joint names in URDF order (excludes type='fixed')."""
    root = ET.fromstring(urdf_text)
    return [
        joint.attrib["name"]
        for joint in root.findall("joint")
        if joint.attrib.get("type") != "fixed"
    ]
