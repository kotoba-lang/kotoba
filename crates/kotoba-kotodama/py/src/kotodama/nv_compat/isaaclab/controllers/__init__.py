"""isaaclab.controllers — high-level joint-space + task-space controllers.

Mirror of `isaaclab.controllers` (Isaac Lab 1.x). Provides drop-in controllers
that consume a current articulation state + a task-space command and emit
joint-space deltas (or torques) for downstream `JointPositionAction` /
`JointEffortAction` to apply.

R1.x scope:
  - DifferentialIKController — Jacobian-based IK (damped least squares /
    pseudoinverse) for arm reaching tasks. Pairs with JointPositionAction.
  - OperationalSpaceController — task-space torque control via Cartesian
    impedance + Jacobian transpose + null-space projection. Pairs with
    JointEffortAction directly.

Future R1.x adds:
  - ImpedanceController — Cartesian stiffness/damping with mass matrix
"""

from .differential_ik import (
    DifferentialIKController,
    DifferentialIKControllerCfg,
)
from .operational_space import (
    OperationalSpaceController,
    OperationalSpaceControllerCfg,
)

__all__ = [
    "DifferentialIKController", "DifferentialIKControllerCfg",
    "OperationalSpaceController", "OperationalSpaceControllerCfg",
]
