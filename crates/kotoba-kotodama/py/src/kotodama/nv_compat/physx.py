"""PhysX 5 public C++ API surface (Pythonized mirror).

Per ADR-2605261800 §D11, PhysX is the 10th compat target. PhysX 5 is BSD-3
which is license-compatible, but the upstream WASM build does not yet exist.
This module exposes the public PhysX C++ API as Python classes, routed to
kotodama.nv_compat._kernel Cartpole dynamics at R1.1.

Naming follows PhysX 5: PxScene / PxRigidDynamic / PxArticulationReducedCoordinate
/ PxArticulationJointReducedCoordinate / PxShape / PxBoxGeometry / PxMaterial.

NVIDIA® / PhysX® are NVIDIA Corporation trademarks; this module is API-compat
only per Google v. Oracle (2021).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional

from ._kernel import (
    ArticulatedSystem,
    CartpoleConfig,
    CartpoleState,
    cartpole_cfg_from_urdf,
    cartpole_step,
    detect_cartpole_topology,
    parse_urdf,
)


class PxArticulationJointType(enum.IntEnum):
    eFIX = 0
    ePRISMATIC = 1
    eREVOLUTE = 2
    eREVOLUTE_UNWRAPPED = 3
    eSPHERICAL = 4


@dataclass
class PxMaterial:
    static_friction: float = 0.5
    dynamic_friction: float = 0.5
    restitution: float = 0.0


@dataclass
class PxBoxGeometry:
    half_extents: tuple[float, float, float] = (0.5, 0.5, 0.5)


@dataclass
class PxShape:
    geometry: PxBoxGeometry
    material: PxMaterial = field(default_factory=PxMaterial)


@dataclass
class PxArticulationJointReducedCoordinate:
    joint_type: PxArticulationJointType
    parent_pose: tuple[float, ...] = (0.0,) * 7
    child_pose: tuple[float, ...] = (0.0,) * 7
    drive_target: float = 0.0
    drive_velocity: float = 0.0
    drive_stiffness: float = 0.0
    drive_damping: float = 0.0

    def setDriveTarget(self, target: float) -> None:
        self.drive_target = target


@dataclass
class PxRigidDynamic:
    """Mirror of physx::PxRigidDynamic (subset)."""
    mass: float = 1.0
    linear_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    angular_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)


class PxArticulationReducedCoordinate:
    """Mirror of physx::PxArticulationReducedCoordinate (subset).

    R1.1: backed by Cartpole closed-form kernel. R1.5 promotes to Featherstone
    multi-link via kami-genesis Rust backend.
    """

    def __init__(self, system: Optional[ArticulatedSystem] = None,
                 urdf_text: Optional[str] = None):
        if system is None:
            if urdf_text is None:
                raise ValueError("provide system or urdf_text")
            system = parse_urdf(urdf_text)
        if not detect_cartpole_topology(system):
            raise NotImplementedError(
                "R1.1 PxArticulationReducedCoordinate handles Cartpole only. "
                "Featherstone arrives at R1.5."
            )
        self.system = system
        self._state = CartpoleState()
        self._applied_force = 0.0
        self._cfg: Optional[CartpoleConfig] = None

    def _bind(self, gravity: float, dt: float) -> None:
        self._cfg = cartpole_cfg_from_urdf(self.system, gravity=gravity, dt=dt)

    def step_internal(self) -> None:
        if self._cfg is None:
            raise RuntimeError("articulation not added to scene")
        cartpole_step(self._state, self._applied_force, self._cfg)
        self._applied_force = 0.0

    def setJointEffort(self, effort: float, joint_index: int = 0) -> None:
        # Cartpole: slider joint index 0; pole effort ignored (pure revolute, undriven).
        if joint_index == 0:
            self._applied_force = effort

    def getJointPositions(self) -> list[float]:
        return [self._state.x, self._state.theta]

    def getJointVelocities(self) -> list[float]:
        return [self._state.x_dot, self._state.theta_dot]


class PxScene:
    """Mirror of physx::PxScene (subset).

    Iterates articulations + rigid bodies via fixed-dt simulate / fetchResults.
    """

    def __init__(self, gravity: tuple[float, float, float] = (0.0, 0.0, -9.81)):
        self.gravity = gravity
        self._dt: Optional[float] = None
        self._articulations: list[PxArticulationReducedCoordinate] = []
        self._rigid_bodies: list[PxRigidDynamic] = []

    def addArticulation(self, art: PxArticulationReducedCoordinate) -> None:
        self._articulations.append(art)
        # bind with |g_z|; positive magnitude expected by kernel
        if self._dt is None:
            self._dt = 1.0 / 60.0
        art._bind(abs(self.gravity[2]), self._dt)

    def addActor(self, body: PxRigidDynamic) -> None:
        self._rigid_bodies.append(body)

    def simulate(self, elapsed_time: float) -> None:
        # Stash dt; PxScene::fetchResults() applies it.
        self._dt = elapsed_time
        if self._articulations and self._articulations[0]._cfg is None:
            for a in self._articulations:
                a._bind(abs(self.gravity[2]), elapsed_time)
        for a in self._articulations:
            if a._cfg is not None:
                a._cfg.dt = elapsed_time

    def fetchResults(self, block: bool = True) -> bool:
        if self._dt is None:
            return False
        for a in self._articulations:
            a.step_internal()
        return True

    def getArticulations(self) -> list[PxArticulationReducedCoordinate]:
        return list(self._articulations)
