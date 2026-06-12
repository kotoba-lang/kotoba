"""ActuatorNetMLP — residual-MLP actuator dynamics (stub).

Mirror of `isaaclab.actuators.ActuatorNetMLP` (Isaac Lab 1.x). The upstream
class wraps a small trained MLP that predicts torque given (joint_pos,
joint_vel, target_pos, target_vel) history. Used to capture series-elastic
actuator dynamics that an ideal PD model misses (backlash, friction,
gearbox compliance, etc.).

In nv_compat the surface mirrors the API so app code ports cleanly, but
without weights loaded the actuator falls back to ImplicitActuator PD
plus an additive correction the host can install via `set_correction_fn`.
This keeps the runtime contract intact while leaving real network
inference to a later iter (or to a host-supplied weights file).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from .actuator_implicit import ImplicitActuator, ImplicitActuatorCfg


@dataclass
class ActuatorNetMLPCfg(ImplicitActuatorCfg):
    """Cfg for ActuatorNetMLP.

    `network_file`   — path to weights (consumed by a future loader; current
                       stub records the path on the cfg for downstream tools)
    `input_size`     — history length × features (informational here)
    `output_size`    — torque dim (typically 1 per joint)
    `pos_scale` / `vel_scale` / `torque_scale` — normalization scales used
                       by the underlying network. Forwarded through the
                       cfg dataclass; not consumed by the stub compute.
    """
    network_file: str = ""
    input_size: int = 30
    output_size: int = 1
    pos_scale: float = 1.0
    vel_scale: float = 0.05
    torque_scale: float = 1.0


class ActuatorNetMLP(ImplicitActuator):
    """Stub actuator-net actuator. Falls back to ImplicitActuator PD when
    no `correction_fn` is registered; with a correction fn registered the
    returned torque is `tau_pd + correction_fn(q, dq, q_target, dq_target)`.
    """

    cfg: ActuatorNetMLPCfg

    def __init__(self, cfg: ActuatorNetMLPCfg):
        super().__init__(cfg)
        self._correction_fn: Optional[Callable[..., List[float]]] = None
        # Hidden state for callers that want temporal correction (e.g.
        # LSTM-style ActuatorNetLSTM). Plain MLP correction can ignore it.
        self._hidden_state: Any = None

    # ── correction hook ──────────────────────────────────────────────────

    def set_correction_fn(
        self,
        fn: Callable[[List[float], List[float], List[float], List[float]], List[float]],
    ) -> None:
        """Register the residual-MLP forward function.

        `fn(q, dq, q_target, dq_target) -> List[float]` MUST return a
        length-`num_joints` correction torque vector. Called per `compute()`
        in addition to the PD term.
        """
        self._correction_fn = fn

    def reset(self) -> None:
        super().reset()
        self._hidden_state = None

    @property
    def has_network(self) -> bool:
        """True when a correction fn (or network weights) is loaded."""
        return self._correction_fn is not None

    # ── compute ──────────────────────────────────────────────────────────

    def _compute_torque(
        self,
        q: List[float], dq: List[float],
        q_target: List[float], dq_target: List[float],
    ) -> List[float]:
        # Always compute the PD baseline.
        pd_term = super()._compute_torque(q, dq, q_target, dq_target)
        if self._correction_fn is None:
            return pd_term
        correction = self._correction_fn(q, dq, q_target, dq_target)
        if len(correction) != self.num_joints:
            raise ValueError(
                f"correction_fn returned {len(correction)} elements; "
                f"expected {self.num_joints}"
            )
        return [pd_term[i] + correction[i] for i in range(self.num_joints)]
