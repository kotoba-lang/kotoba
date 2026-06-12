"""nv_compat.dynamics — generic articulated-body dynamics solvers.

Mirrors the parts of NVIDIA PhysX's `PxArticulationReducedCoordinate`
that are needed for forward dynamics simulation of arbitrary kinematic
trees (Franka 7-DoF, ANYmal 12-DoF + floating base, etc.). Replaces
the topology-specialised closed-form integrators in `_kernel.py`
(Cartpole / DoublePendulum) which don't scale past 2 DoF.

R1.x scope:
  - articulated_dynamics — Featherstone's Articulated-Body Algorithm
    (ABA) O(n) forward dynamics + semi-implicit Euler integration.

Future iterations:
  - composite_rigid_body — CRBA for joint-space inertia matrix M(q)
  - rnea — recursive Newton-Euler for inverse dynamics τ(q, qdot, qddot)
  - contact_solver — Coulomb friction LCP for ground contacts (locomotion)
  - constraint_solver — bilateral constraints (closed-chain mechanisms)

Trademark: "PhysX®" is a trademark of NVIDIA Corporation. This module
is API namespace localization per ADR-2605261800 §D6+§D11 / Google v.
Oracle 2021 API fair use. The canonical religious-corp impl is
kami-articulated (40-engine/kami-engine/kami-articulated/).
"""

from .articulated_dynamics import (
    aba_forward,
    articulated_step,
    ArticulatedState,
    BuiltArticulation,
    build_articulation,
    coriolis_gravity_vector,
    crba_mass_matrix,
    forward_kinematics,
    geometric_jacobian,
    kinetic_energy,
    rnea_inverse_dynamics,
    spatial_inertia_from_link,
)

__all__ = [
    "aba_forward",
    "articulated_step",
    "ArticulatedState",
    "BuiltArticulation",
    "build_articulation",
    "coriolis_gravity_vector",
    "crba_mass_matrix",
    "forward_kinematics",
    "geometric_jacobian",
    "kinetic_energy",
    "rnea_inverse_dynamics",
    "spatial_inertia_from_link",
]
