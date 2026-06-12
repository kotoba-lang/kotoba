"""isaaclab.envs.mdp — Manager-Based MDP term builders + standard functions.

Mirrors `isaaclab.envs.mdp` (Isaac Lab 1.x). Provides the building blocks
for composing RL environments declaratively via observation/reward/event
term groups. Standard mdp.* functions cover the canonical Cartpole / DP
training surface.

Term classes:
  - ObsTerm   — observation function + params + clip/scale
  - RewTerm   — reward function + weight + params
  - EventTerm — reset/event hook function + params

Group classes:
  - ObsGroup  — composes multiple ObsTerm into a single observation vector
  - RewGroup  — composes multiple RewTerm into a scalar reward (sum of weighted)
  - EventGroup — composes EventTerm into a reset/event handler

Standard mdp.* functions:
  - observations: joint_pos_rel, joint_vel_rel, base_lin_vel, base_ang_vel,
                  last_action, generated_commands
  - rewards: is_alive, is_terminated, joint_pos_l2, joint_vel_l2, action_l2,
             action_rate_l2, joint_torques_l2
  - events: reset_joints_by_offset, reset_joints_to_default,
            randomize_rigid_body_mass, randomize_rigid_body_material
  - commands: CommandGeneratorBase + NullCommand + UniformVelocityCommand
              + UniformPose3DCommand (random per-env goal targets with
              resampling interval; integrates with mdp.generated_commands)
  - actions:  ActionManager + JointEffortAction / JointPositionAction /
              JointVelocityAction (action vector composition + dispatch
              onto env effort buffers; PD/P controllers for position/velocity
              target modes)
  - curriculums: CurriculumManager + terrain_levels_vy / modify_reward_weight
                 / modify_action_scale (gradual task-difficulty progression
                 for quadruped locomotion tasks; composes with iter 44
                 TerrainImporter.update_env_origins)

stdlib-only.
"""

from .actions import (
    ActionManager,
    ActionTerm,
    ActionTermCfgBase,
    BinaryJointPositionAction,
    BinaryJointPositionActionCfg,
    DifferentialInverseKinematicsAction,
    DifferentialInverseKinematicsActionCfg,
    JointEffortAction,
    JointEffortActionCfg,
    JointPositionAction,
    JointPositionActionCfg,
    JointVelocityAction,
    JointVelocityActionCfg,
    NonHolonomicAction,
    NonHolonomicActionCfg,
    OperationalSpaceControllerAction,
    OperationalSpaceControllerActionCfg,
)
from .commands import (
    CommandCfgBase,
    CommandGeneratorBase,
    NullCommand,
    UniformPose3DCommand,
    UniformPose3DCommandCfg,
    UniformPose3DRanges,
    UniformVelocityCommand,
    UniformVelocityCommandCfg,
    UniformVelocityRanges,
)
from .curriculums import (
    CurriculumManager,
    CurriculumTerm,
    modify_action_scale,
    modify_reward_weight,
    reset_distance_accumulator,
    terrain_levels_vy,
    update_distance_accumulator,
)
from .terminations import (
    all_of,
    any_of,
    bad_orientation,
    base_contact,
    illegal_contact,
    joint_pos_out_of_limit,
    joint_vel_out_of_limit,
    negate,
    root_height_below_minimum,
    time_out,
)
from .events import (
    EventTerm,
    apply_external_force_torque,
    push_by_setting_velocity,
    randomize_actuator_gains,
    randomize_com,
    randomize_friction,
    randomize_initial_root_pose,
    randomize_mass,
    randomize_rigid_body_mass,
    reset_joints_by_offset,
    reset_joints_to_default,
)
from .observations import (
    ObsGroup,
    ObsTerm,
    base_ang_vel,
    base_ang_vel_b,
    base_lin_vel,
    base_lin_vel_b,
    base_lin_vel_w,
    base_pos_z,
    generated_commands,
    height_scan,
    joint_pos_rel,
    joint_pos_rel_default,
    joint_vel_rel,
    last_action,
    last_action_clipped,
    projected_gravity,
)
from .rewards import (
    RewGroup,
    RewTerm,
    action_l2,
    action_rate_l2,
    alive_bonus,
    ang_vel_xy_l2,
    dof_pos_limits,
    dof_torques_l2,
    feet_air_time,
    flat_orientation_l2,
    is_alive,
    is_terminated,
    joint_pos_l2,
    joint_torques_l2,
    joint_vel_l2,
    lin_vel_z_l2,
    track_ang_vel_z_exp,
    track_lin_vel_xy_exp,
)

__all__ = [
    # Term classes
    "ObsTerm", "RewTerm", "EventTerm",
    "ObsGroup", "RewGroup",
    # Observation functions
    "joint_pos_rel", "joint_vel_rel",
    "base_lin_vel", "base_ang_vel",
    "last_action", "generated_commands",
    # Locomotion observation extensions (iter 61)
    "base_pos_z", "base_lin_vel_w", "base_lin_vel_b", "base_ang_vel_b",
    "projected_gravity", "joint_pos_rel_default", "last_action_clipped",
    "height_scan",
    # Reward functions
    "is_alive", "is_terminated",
    "joint_pos_l2", "joint_vel_l2",
    "action_l2", "action_rate_l2", "joint_torques_l2",
    # Locomotion reward extensions (iter 60)
    "track_lin_vel_xy_exp", "track_ang_vel_z_exp",
    "flat_orientation_l2", "lin_vel_z_l2", "ang_vel_xy_l2",
    "feet_air_time", "dof_pos_limits", "dof_torques_l2", "alive_bonus",
    # Event functions
    "reset_joints_by_offset", "reset_joints_to_default",
    "randomize_rigid_body_mass",
    # Domain-randomization event extensions (iter 62)
    "push_by_setting_velocity", "randomize_actuator_gains",
    "apply_external_force_torque", "randomize_friction", "randomize_com",
    "randomize_mass", "randomize_initial_root_pose",
    # Command generators
    "CommandCfgBase", "CommandGeneratorBase",
    "NullCommand",
    "UniformVelocityCommand", "UniformVelocityCommandCfg", "UniformVelocityRanges",
    "UniformPose3DCommand", "UniformPose3DCommandCfg", "UniformPose3DRanges",
    # Action terms + manager
    "ActionTerm", "ActionTermCfgBase", "ActionManager",
    "JointEffortAction", "JointEffortActionCfg",
    "JointPositionAction", "JointPositionActionCfg",
    "JointVelocityAction", "JointVelocityActionCfg",
    # Task-space action wrappers (iter 64 — compose iter 41 + iter 63 controllers)
    "DifferentialInverseKinematicsAction", "DifferentialInverseKinematicsActionCfg",
    "OperationalSpaceControllerAction", "OperationalSpaceControllerActionCfg",
    # Gripper + mobile-base action wrappers (iter 65)
    "BinaryJointPositionAction", "BinaryJointPositionActionCfg",
    "NonHolonomicAction", "NonHolonomicActionCfg",
    # Curriculum manager + standard fns
    "CurriculumTerm", "CurriculumManager",
    "terrain_levels_vy", "modify_reward_weight", "modify_action_scale",
    "update_distance_accumulator", "reset_distance_accumulator",
    # Termination functions (compose with iter 22 TerminationTerm)
    "time_out", "bad_orientation", "root_height_below_minimum",
    "joint_pos_out_of_limit", "joint_vel_out_of_limit",
    "illegal_contact", "base_contact",
    "any_of", "all_of", "negate",
]
