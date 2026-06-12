"""_kernel — pure-Python Cartpole dynamics + URDF parsing primitives.

Formulas mirror 40-engine/kami-engine/kami-genesis/src/cartpole.rs bit-for-bit.
stdlib-only (xml.etree.ElementTree) to keep Pyodide/WASM build slim.

Used by nv_compat facades:
  - omni.usd            (URDF loader fronting `Stage`)
  - isaacsim.core.api   (`World`, `Articulation`)
  - isaaclab.envs       (`ManagerBasedRLEnv` → `CartpoleEnv`)
  - physx               (`PxScene`, `PxArticulationReducedCoordinate`)
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional


# ---------- URDF parse ----------------------------------------------------------

@dataclass
class Pose:
    xyz: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rpy: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class Inertia:
    mass: float = 0.0
    ixx: float = 0.0
    iyy: float = 0.0
    izz: float = 0.0
    ixy: float = 0.0
    ixz: float = 0.0
    iyz: float = 0.0
    com: Pose = field(default_factory=Pose)


@dataclass
class Link:
    name: str
    inertia: Inertia = field(default_factory=Inertia)


@dataclass
class Joint:
    name: str
    kind: str  # "fixed" | "prismatic" | "revolute" | "continuous"
    parent: str
    child: str
    origin: Pose = field(default_factory=Pose)
    axis: tuple[float, float, float] = (1.0, 0.0, 0.0)
    lower: float = -math.inf
    upper: float = math.inf
    effort: float = 0.0
    velocity: float = 0.0
    damping: float = 0.0
    friction: float = 0.0


@dataclass
class ArticulatedSystem:
    name: str
    links: list[Link]
    joints: list[Joint]


def _parse_triplet(s: Optional[str], default: tuple[float, float, float]) -> tuple[float, float, float]:
    if s is None:
        return default
    parts = s.split()
    if len(parts) != 3:
        raise ValueError(f"expected 3 numbers, got {s!r}")
    return (float(parts[0]), float(parts[1]), float(parts[2]))


def parse_urdf(xml_text: str) -> ArticulatedSystem:
    """Parse URDF XML. Supports prismatic + revolute + fixed + continuous joints.

    Mirrors kami_articulated::parse_urdf (Rust). Cartpole-class topology coverage.
    """
    root = ET.fromstring(xml_text)
    name = root.get("name", "robot")
    links: list[Link] = []
    joints: list[Joint] = []

    for el in root:
        if el.tag == "link":
            link = Link(name=el.get("name", ""))
            inertial = el.find("inertial")
            if inertial is not None:
                origin = inertial.find("origin")
                if origin is not None:
                    link.inertia.com = Pose(
                        xyz=_parse_triplet(origin.get("xyz"), (0, 0, 0)),
                        rpy=_parse_triplet(origin.get("rpy"), (0, 0, 0)),
                    )
                mass = inertial.find("mass")
                if mass is not None:
                    link.inertia.mass = float(mass.get("value", "0"))
                ie = inertial.find("inertia")
                if ie is not None:
                    link.inertia.ixx = float(ie.get("ixx", "0"))
                    link.inertia.iyy = float(ie.get("iyy", "0"))
                    link.inertia.izz = float(ie.get("izz", "0"))
                    link.inertia.ixy = float(ie.get("ixy", "0"))
                    link.inertia.ixz = float(ie.get("ixz", "0"))
                    link.inertia.iyz = float(ie.get("iyz", "0"))
            links.append(link)
        elif el.tag == "joint":
            kind = el.get("type", "fixed")
            if kind not in ("fixed", "prismatic", "revolute", "continuous"):
                raise ValueError(f"unsupported joint type: {kind}")
            parent_el = el.find("parent")
            child_el = el.find("child")
            if parent_el is None or child_el is None:
                raise ValueError(f"joint {el.get('name')} missing parent/child")
            j = Joint(
                name=el.get("name", ""),
                kind=kind,
                parent=parent_el.get("link", ""),
                child=child_el.get("link", ""),
            )
            origin = el.find("origin")
            if origin is not None:
                j.origin = Pose(
                    xyz=_parse_triplet(origin.get("xyz"), (0, 0, 0)),
                    rpy=_parse_triplet(origin.get("rpy"), (0, 0, 0)),
                )
            axis = el.find("axis")
            if axis is not None:
                j.axis = _parse_triplet(axis.get("xyz"), (1, 0, 0))
            limit = el.find("limit")
            if limit is not None:
                j.lower = float(limit.get("lower", "-inf"))
                j.upper = float(limit.get("upper", "inf"))
                j.effort = float(limit.get("effort", "0"))
                j.velocity = float(limit.get("velocity", "0"))
            dynamics = el.find("dynamics")
            if dynamics is not None:
                j.damping = float(dynamics.get("damping", "0"))
                j.friction = float(dynamics.get("friction", "0"))
            joints.append(j)
    return ArticulatedSystem(name=name, links=links, joints=joints)


# ---------- Cartpole closed-form dynamics --------------------------------------

@dataclass
class CartpoleConfig:
    cart_mass: float = 1.0
    pole_mass: float = 0.1
    pole_half_length: float = 0.25   # half of 0.5 m total
    gravity: float = 9.81
    force_mag: float = 100.0
    dt: float = 1.0 / 60.0


@dataclass
class CartpoleState:
    x: float = 0.0
    x_dot: float = 0.0
    theta: float = 0.0
    theta_dot: float = 0.0


def cartpole_step(state: CartpoleState, action: float, cfg: CartpoleConfig) -> None:
    """One semi-implicit Euler step. Matches kami_genesis::cartpole::CartpoleState::step."""
    force = max(-cfg.force_mag, min(cfg.force_mag, action))
    sin_t = math.sin(state.theta)
    cos_t = math.cos(state.theta)
    total_mass = cfg.cart_mass + cfg.pole_mass
    pml = cfg.pole_mass * cfg.pole_half_length
    temp = (force + pml * state.theta_dot * state.theta_dot * sin_t) / total_mass
    theta_acc = (cfg.gravity * sin_t - cos_t * temp) / (
        cfg.pole_half_length * (4.0 / 3.0 - cfg.pole_mass * cos_t * cos_t / total_mass)
    )
    x_acc = temp - pml * theta_acc * cos_t / total_mass
    state.x_dot += cfg.dt * x_acc
    state.x += cfg.dt * state.x_dot
    state.theta_dot += cfg.dt * theta_acc
    state.theta += cfg.dt * state.theta_dot


def detect_cartpole_topology(sys: ArticulatedSystem) -> bool:
    """True if `sys` is a Cartpole topology (1 prismatic-to-world + 1 revolute, 2 DoF total)."""
    has_prismatic_to_world = any(
        j.kind == "prismatic" and j.parent == "world" for j in sys.joints
    )
    revolute_count = sum(1 for j in sys.joints if j.kind == "revolute")
    moving_dofs = sum(1 for j in sys.joints if j.kind in ("prismatic", "revolute"))
    return has_prismatic_to_world and revolute_count == 1 and moving_dofs == 2


def cartpole_cfg_from_urdf(sys: ArticulatedSystem, gravity: float, dt: float) -> CartpoleConfig:
    """Extract a CartpoleConfig from a parsed URDF system."""
    if not detect_cartpole_topology(sys):
        raise ValueError(f"system `{sys.name}` is not a Cartpole topology")
    cart = next(l for l in sys.links if l.name == "cart")
    pole = next(l for l in sys.links if l.name == "pole_link")
    slider = next(j for j in sys.joints if j.kind == "prismatic")
    return CartpoleConfig(
        cart_mass=cart.inertia.mass,
        pole_mass=pole.inertia.mass,
        pole_half_length=0.25,  # matches URDF cylinder length 0.5
        gravity=gravity,
        force_mag=max(slider.effort, 1.0),
        dt=dt,
    )


# ---------- Double pendulum (2-link revolute serial chain) ---------------------

@dataclass
class DoublePendulumConfig:
    m1: float = 1.0
    m2: float = 1.0
    l1: float = 1.0
    l2: float = 1.0
    gravity: float = 9.81
    effort_limit: float = 50.0
    dt: float = 1.0 / 240.0


@dataclass
class DoublePendulumState:
    q1: float = 0.0
    q2: float = 0.0
    q1_dot: float = 0.0
    q2_dot: float = 0.0


def double_pendulum_step(s: DoublePendulumState, tau: tuple[float, float], cfg: DoublePendulumConfig) -> None:
    """Semi-implicit Euler step. Mirrors kami_genesis::double_pendulum bit-for-bit."""
    t1 = max(-cfg.effort_limit, min(cfg.effort_limit, tau[0]))
    t2 = max(-cfg.effort_limit, min(cfg.effort_limit, tau[1]))
    lc1 = cfg.l1 * 0.5
    lc2 = cfg.l2 * 0.5
    i1 = cfg.m1 * cfg.l1 * cfg.l1 / 12.0
    i2 = cfg.m2 * cfg.l2 * cfg.l2 / 12.0
    s2 = math.sin(s.q2)
    c2 = math.cos(s.q2)
    s1 = math.sin(s.q1)
    s12 = math.sin(s.q1 + s.q2)
    m11 = (
        cfg.m1 * lc1 * lc1
        + cfg.m2 * (cfg.l1 * cfg.l1 + lc2 * lc2 + 2.0 * cfg.l1 * lc2 * c2)
        + i1
        + i2
    )
    m12 = cfg.m2 * (lc2 * lc2 + cfg.l1 * lc2 * c2) + i2
    m22 = cfg.m2 * lc2 * lc2 + i2
    h = -cfg.m2 * cfg.l1 * lc2 * s2
    c_1 = h * s.q2_dot * (2.0 * s.q1_dot + s.q2_dot)
    c_2 = -h * s.q1_dot * s.q1_dot
    g1 = (cfg.m1 * lc1 + cfg.m2 * cfg.l1) * cfg.gravity * s1 + cfg.m2 * lc2 * cfg.gravity * s12
    g2 = cfg.m2 * lc2 * cfg.gravity * s12
    b1 = t1 - c_1 - g1
    b2 = t2 - c_2 - g2
    det = m11 * m22 - m12 * m12
    q1_acc = (m22 * b1 - m12 * b2) / det
    q2_acc = (-m12 * b1 + m11 * b2) / det
    s.q1_dot += cfg.dt * q1_acc
    s.q1 += cfg.dt * s.q1_dot
    s.q2_dot += cfg.dt * q2_acc
    s.q2 += cfg.dt * s.q2_dot


def detect_double_pendulum_topology(sys: ArticulatedSystem) -> bool:
    """True if `sys` is a 2-revolute serial chain rooted at `world`."""
    revolutes = [j for j in sys.joints if j.kind == "revolute"]
    no_prismatic = not any(j.kind == "prismatic" for j in sys.joints)
    return (
        len(revolutes) == 2
        and no_prismatic
        and revolutes[0].parent == "world"
        and revolutes[1].parent == revolutes[0].child
    )


def double_pendulum_cfg_from_urdf(sys: ArticulatedSystem, gravity: float, dt: float) -> DoublePendulumConfig:
    if not detect_double_pendulum_topology(sys):
        raise ValueError(f"system `{sys.name}` is not a double pendulum topology")
    revolutes = [j for j in sys.joints if j.kind == "revolute"]
    link1 = next(l for l in sys.links if l.name == revolutes[0].child)
    link2 = next(l for l in sys.links if l.name == revolutes[1].child)
    l1 = max(abs(revolutes[1].origin.xyz[2]), 1e-3)
    l2 = abs(link2.inertia.com.xyz[2]) * 2.0
    return DoublePendulumConfig(
        m1=link1.inertia.mass,
        m2=link2.inertia.mass,
        l1=l1,
        l2=l2 if l2 > 1e-3 else l1,
        gravity=gravity,
        effort_limit=max(revolutes[0].effort, revolutes[1].effort, 1.0),
        dt=dt,
    )
