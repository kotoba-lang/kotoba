"""isaaclab.envs — Manager + Direct + MARL env families + mdp + task registry + common types."""

from __future__ import annotations

from . import mdp
from .cartpole_direct_env import CartpoleDirectEnv, CartpoleDirectEnvCfg
from .common import (
    BoxSpaceCfg,
    DictSpaceCfg,
    DiscreteSpaceCfg,
    MultiBinarySpaceCfg,
    MultiDiscreteSpaceCfg,
    SpaceCfgBase,
    TupleSpaceCfg,
    VecEnvObs,
    VecEnvResetReturn,
    VecEnvStepReturn,
    dict_to_spec,
    flatten_obs,
    infer_action_dim,
    infer_observation_shape,
    space_shape,
    spec_to_dict,
)
from .direct_marl_env import DirectMARLEnv, DirectMARLEnvCfg
from .observation_buffers import (
    ObservationHistoryBuffer,
    RewardScaling,
    RunningMeanStd,
)
from .replay_buffer import (
    NStepReplayBuffer,
    PrioritizedReplayBuffer,
    ReplayBuffer,
    Transition,
)
from .direct_rl_env import DirectRLEnv, DirectRLEnvCfg, SimCfg
from .manager_based_rl_env import CartpoleEnvCfg, ManagerBasedRLEnv
from .task_registry import (
    TaskSpec,
    all_task_ids,
    clear_registry,
    get_task_spec,
    make,
    num_registered,
    parse_env_cfg,
    register,
    unregister,
)
from .two_cartpole_marl_env import TwoCartpoleMARLEnv, TwoCartpoleMARLEnvCfg

__all__ = [
    "ManagerBasedRLEnv", "CartpoleEnvCfg",
    "DirectRLEnv", "DirectRLEnvCfg", "SimCfg",
    "CartpoleDirectEnv", "CartpoleDirectEnvCfg",
    "DirectMARLEnv", "DirectMARLEnvCfg",
    "TwoCartpoleMARLEnv", "TwoCartpoleMARLEnvCfg",
    "mdp",
    # task registry
    "TaskSpec", "register", "unregister", "get_task_spec",
    "all_task_ids", "num_registered", "clear_registry",
    "make", "parse_env_cfg",
    # common types + spaces
    "VecEnvObs", "VecEnvStepReturn", "VecEnvResetReturn",
    "SpaceCfgBase", "BoxSpaceCfg", "DiscreteSpaceCfg",
    "MultiDiscreteSpaceCfg", "MultiBinarySpaceCfg",
    "DictSpaceCfg", "TupleSpaceCfg",
    "spec_to_dict", "dict_to_spec",
    "flatten_obs", "infer_action_dim", "infer_observation_shape", "space_shape",
    # observation buffers
    "ObservationHistoryBuffer", "RunningMeanStd", "RewardScaling",
    # replay buffers
    "Transition", "ReplayBuffer", "PrioritizedReplayBuffer", "NStepReplayBuffer",
]
