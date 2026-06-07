"""ImplicitActuator + IdealPDActuator — PD-controlled joint actuators.

Mirror of `isaaclab.actuators.ImplicitActuator` (Isaac Lab 1.x). The
canonical "ideal PD" actuator group:

    tau = K_p (q_target - q) - K_d (dq_target - dq)

With `dq_target = 0` (the common case for position control) this reduces
to the textbook PD:

    tau = K_p (q_target - q) - K_d (dq)

Both PD gains can be uniform ({"all": value}) or per-joint
({joint_idx_in_group: value}).

`IdealPDActuator` is a name-alias of `ImplicitActuator` — Isaac Lab keeps
both names for backward compat; we mirror that.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .actuator_base import ActuatorBase, ActuatorBaseCfg


@dataclass
class ImplicitActuatorCfg(ActuatorBaseCfg):
    """Cfg for ImplicitActuator. No fields beyond ActuatorBaseCfg —
    stiffness/damping/effort_limit/velocity_limit cover the surface."""


class ImplicitActuator(ActuatorBase):
    """Standard PD actuator group."""

    def _compute_torque(
        self,
        q: List[float], dq: List[float],
        q_target: List[float], dq_target: List[float],
    ) -> List[float]:
        return [
            self.stiffness[i] * (q_target[i] - q[i])
            - self.damping[i] * (dq[i] - dq_target[i])
            for i in range(self.num_joints)
        ]


# ── IdealPDActuator — alias (matches Isaac Lab) ─────────────────────────


@dataclass
class IdealPDActuatorCfg(ImplicitActuatorCfg):
    """Alias of ImplicitActuatorCfg — kept for Isaac Lab API parity."""


class IdealPDActuator(ImplicitActuator):
    """Alias of ImplicitActuator — kept for Isaac Lab API parity."""
