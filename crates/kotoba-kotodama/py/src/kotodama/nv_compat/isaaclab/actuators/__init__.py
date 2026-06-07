"""isaaclab.actuators — joint actuator dynamics models.

Mirror of `isaaclab.actuators` (Isaac Lab 1.x). Sits between iter 40 action
terms (high-level joint targets) and iter 43 Articulation (low-level joint
state). Each actuator group owns a subset of joints + shared PD gains +
effort/velocity limits, and produces the actual torque applied to the
articulation per step.

R1.x scope:
  - ActuatorBaseCfg / ActuatorBase  — abstract base + reset() / compute()
  - ImplicitActuatorCfg / ImplicitActuator
        Standard PD: tau = K_p (q_target - q) - K_d (dq_target - dq).
        Optional effort_limit + velocity_limit hard clips.
  - IdealPDActuatorCfg / IdealPDActuator
        Thin alias of ImplicitActuator — Isaac Lab keeps both names for
        backward compat; we follow that convention.
  - DCMotorCfg / DCMotor
        Brushed-DC speed-torque curve. tau = K_p(q_t - q) - K_d(dq) but
        the result is clipped by a velocity-dependent torque ceiling
        (linear interpolation from stall torque at dq=0 to zero at
        no-load speed). Models real-world motor saturation.
  - ActuatorNetMLPCfg / ActuatorNetMLP
        Residual-MLP actuator dynamics stub. compute() falls back to
        ImplicitActuator PD when no weights are loaded; matches the
        upstream "ActuatorNet" surface for app porting without forcing
        a neural-net load path here.

Standard usage:

    cfg = ImplicitActuatorCfg(
        joint_names=[0, 1],
        stiffness={"all": 100.0},   # or per-joint dict
        damping={"all": 10.0},
        effort_limit=50.0,
        velocity_limit=10.0,
    )
    act = ImplicitActuator(cfg)
    tau = act.compute(
        joint_pos=[0.1, 0.0], joint_vel=[0.0, 0.0],
        joint_pos_target=[0.0, 0.5], joint_vel_target=[0.0, 0.0],
    )
    # → [-10.0, 50.0]  (each PD; effort_limit=50 clips term 1)

Pure stdlib.
"""

from .actuator_base import ActuatorBase, ActuatorBaseCfg
from .actuator_dc_motor import DCMotor, DCMotorCfg
from .actuator_implicit import (
    IdealPDActuator,
    IdealPDActuatorCfg,
    ImplicitActuator,
    ImplicitActuatorCfg,
)
from .actuator_net import ActuatorNetMLP, ActuatorNetMLPCfg

__all__ = [
    "ActuatorBaseCfg", "ActuatorBase",
    "ImplicitActuatorCfg", "ImplicitActuator",
    "IdealPDActuatorCfg", "IdealPDActuator",
    "DCMotorCfg", "DCMotor",
    "ActuatorNetMLPCfg", "ActuatorNetMLP",
]
