"""DCMotor — brushed-DC actuator with speed-torque saturation.

Mirror of `isaaclab.actuators.DCMotor` (Isaac Lab 1.x). Models the real-
world torque-velocity curve of a brushed DC motor:

    1. Compute PD demand: tau_pd = K_p (q_t - q) - K_d (dq - dq_t)
    2. Compute speed-clipped ceiling for current dq:
         tau_max(dq) = stall_torque * max(0, 1 - |dq| / no_load_speed)
       (linear from stall_torque at dq=0 to zero at no_load_speed)
    3. Clip: tau = clamp(tau_pd, -tau_max(dq), +tau_max(dq))
    4. Apply ActuatorBase effort_limit + velocity_limit on top

Real motors also have viscous damping + friction; those are folded into
the PD damping term + the speed-saturation curve respectively.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .actuator_base import ActuatorBase, ActuatorBaseCfg


@dataclass
class DCMotorCfg(ActuatorBaseCfg):
    """Cfg for DCMotor.

    `saturation_effort` — stall torque (max torque at dq=0). When 0 or
                           None, defaults to effort_limit (so the speed-
                           saturation ceiling matches the hard effort cap).
    `velocity_limit`    — interpreted as the motor's no-load speed; the
                          torque ceiling drops linearly from saturation_effort
                          at dq=0 to 0 at |dq|=velocity_limit.

    velocity_limit MUST be > 0 for the speed-saturation curve to be
    meaningful; if it's None, falls back to ImplicitActuator semantics.
    """
    saturation_effort: float = 0.0  # 0 = use effort_limit


class DCMotor(ActuatorBase):
    """Brushed-DC actuator with linear speed-torque curve."""

    cfg: DCMotorCfg

    def _compute_torque(
        self,
        q: List[float], dq: List[float],
        q_target: List[float], dq_target: List[float],
    ) -> List[float]:
        cfg: DCMotorCfg = self.cfg  # type: ignore[assignment]
        # PD demand.
        tau_pd = [
            self.stiffness[i] * (q_target[i] - q[i])
            - self.damping[i] * (dq[i] - dq_target[i])
            for i in range(self.num_joints)
        ]
        # Speed-saturation ceiling.
        saturation = (
            cfg.saturation_effort if cfg.saturation_effort > 0.0
            else (cfg.effort_limit if cfg.effort_limit is not None else 0.0)
        )
        if saturation <= 0.0 or cfg.velocity_limit is None or cfg.velocity_limit <= 0:
            return tau_pd  # no saturation curve to apply
        vlim = cfg.velocity_limit
        out: List[float] = []
        for i in range(self.num_joints):
            speed_factor = max(0.0, 1.0 - abs(dq[i]) / vlim)
            tau_max = saturation * speed_factor
            out.append(max(-tau_max, min(tau_max, tau_pd[i])))
        return out

    def _apply_limits(self, tau: List[float], dq: List[float]) -> List[float]:
        """Override: DCMotor handles velocity_limit internally via the
        speed-saturation curve, so skip ActuatorBase's velocity_limit
        clamp (it would double-apply). effort_limit still applies."""
        cfg = self.cfg
        out = list(tau)
        if cfg.effort_limit is not None:
            lim = cfg.effort_limit
            out = [max(-lim, min(lim, t)) for t in out]
        return out
