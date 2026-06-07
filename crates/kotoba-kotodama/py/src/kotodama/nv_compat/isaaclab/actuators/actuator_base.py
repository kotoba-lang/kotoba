"""ActuatorBase — abstract base for actuator groups.

An actuator group owns a subset of joints (by integer index) + shared PD
gains. Subclasses implement `compute(joint_pos, joint_vel, joint_pos_target,
joint_vel_target)` returning a torque vector matching `joint_names` order.

`stiffness` / `damping` accept either:
  - {"all": float}                — same value for every joint in the group
  - {joint_idx: float}            — per-joint overrides (missing → 0)
  - float (legacy)                — shorthand for {"all": value}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


def _resolve_gains(spec: Any, joint_count: int) -> List[float]:
    """Resolve a stiffness/damping spec into a per-joint list."""
    if isinstance(spec, (int, float)):
        return [float(spec)] * joint_count
    if isinstance(spec, dict):
        if "all" in spec:
            return [float(spec["all"])] * joint_count
        # Per-index dict (keys are joint indices in the group's order).
        return [float(spec.get(i, 0.0)) for i in range(joint_count)]
    raise TypeError(
        f"stiffness/damping must be float or dict; got {type(spec).__name__}"
    )


@dataclass
class ActuatorBaseCfg:
    """Common cfg fields shared by every actuator subtype.

    `joint_names` is a list of integer joint indices the actuator group
    drives. (Upstream Isaac Lab uses joint NAME strings + regex matching;
    we keep it index-based here for kernel-level clarity, matching iter
    40 ActionTermCfgBase.)

    `effort_limit` / `velocity_limit` are hard clips applied after the
    actuator's torque calculation. None = no clip.
    """
    joint_names: List[int] = field(default_factory=list)
    stiffness: Any = field(default_factory=lambda: {"all": 0.0})
    damping: Any = field(default_factory=lambda: {"all": 0.0})
    effort_limit: Optional[float] = None
    velocity_limit: Optional[float] = None


class ActuatorBase:
    """Abstract actuator group. Subclasses implement `_compute_torque`."""

    cfg: ActuatorBaseCfg

    def __init__(self, cfg: ActuatorBaseCfg):
        if not cfg.joint_names:
            raise ValueError(
                f"{type(self).__name__}.cfg.joint_names must be non-empty"
            )
        if cfg.effort_limit is not None and cfg.effort_limit < 0:
            raise ValueError(
                f"effort_limit must be ≥ 0; got {cfg.effort_limit}"
            )
        if cfg.velocity_limit is not None and cfg.velocity_limit < 0:
            raise ValueError(
                f"velocity_limit must be ≥ 0; got {cfg.velocity_limit}"
            )
        self.cfg = cfg
        n = len(cfg.joint_names)
        self.num_joints = n
        # Resolve gains into per-joint lists.
        self.stiffness: List[float] = _resolve_gains(cfg.stiffness, n)
        self.damping: List[float] = _resolve_gains(cfg.damping, n)
        # Last-computed torque (for introspection / logging).
        self.applied_torque: List[float] = [0.0] * n

    # ── public API ───────────────────────────────────────────────────────

    def compute(
        self,
        joint_pos: List[float],
        joint_vel: List[float],
        joint_pos_target: List[float],
        joint_vel_target: Optional[List[float]] = None,
    ) -> List[float]:
        """Compute per-joint torque for this group.

        Reads only the joint indices in cfg.joint_names from `joint_pos` /
        `joint_vel` (full articulation arrays); writes a torque vector
        matching `joint_names` order (length num_joints).
        """
        if joint_vel_target is None:
            joint_vel_target = [0.0] * self.num_joints
        if (
            len(joint_pos_target) != self.num_joints
            or len(joint_vel_target) != self.num_joints
        ):
            raise ValueError(
                f"target vectors must have length {self.num_joints}"
            )
        # Pull this group's current state from the full articulation state.
        q = [joint_pos[j] if j < len(joint_pos) else 0.0
             for j in self.cfg.joint_names]
        dq = [joint_vel[j] if j < len(joint_vel) else 0.0
              for j in self.cfg.joint_names]
        # Subclass-specific torque.
        tau = self._compute_torque(
            q, dq, joint_pos_target, joint_vel_target,
        )
        # Apply effort / velocity clips.
        tau = self._apply_limits(tau, dq)
        self.applied_torque = list(tau)
        return tau

    def reset(self) -> None:
        """Reset internal state. Default no-op; subclasses with hysteresis
        (e.g. ActuatorNet hidden state) may override."""
        self.applied_torque = [0.0] * self.num_joints

    # ── subclass hooks ───────────────────────────────────────────────────

    def _compute_torque(
        self,
        q: List[float], dq: List[float],
        q_target: List[float], dq_target: List[float],
    ) -> List[float]:
        raise NotImplementedError(
            f"{type(self).__name__} must implement _compute_torque"
        )

    def _apply_limits(self, tau: List[float], dq: List[float]) -> List[float]:
        """Apply effort + velocity-based torque clips."""
        cfg = self.cfg
        out = list(tau)
        # Effort limit.
        if cfg.effort_limit is not None:
            lim = cfg.effort_limit
            out = [max(-lim, min(lim, t)) for t in out]
        # Velocity limit — torque drops to 0 when |dq| ≥ velocity_limit
        # (matches Isaac Lab's saturated-actuator clamp; soft variant in
        # DCMotor uses a linear interpolation instead).
        if cfg.velocity_limit is not None:
            vlim = cfg.velocity_limit
            for i in range(len(out)):
                if abs(dq[i]) >= vlim:
                    # If moving in the same direction the torque would
                    # accelerate further → clamp; otherwise allow braking.
                    if (out[i] > 0 and dq[i] > 0) or (out[i] < 0 and dq[i] < 0):
                        out[i] = 0.0
        return out
