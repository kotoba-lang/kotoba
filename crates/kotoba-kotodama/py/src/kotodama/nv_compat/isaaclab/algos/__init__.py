"""isaaclab.algos — RL training algorithms (kami-native subset).

R1.x scope:
  - CEM (Cross-Entropy Method): pure-stdlib ES-style trainer for low-DOF
    control tasks (Cartpole 4-obs × 1-act). No PyTorch/numpy dependency.
  - PPO (Proximal Policy Optimization): stdlib-only policy-gradient trainer
    with manual-backprop 2-layer MLP, diagonal Gaussian policy, GAE-λ, and
    Adam optimizer. The canonical Isaac Lab RL algorithm.
  - SAC (Soft Actor-Critic): off-policy MaxEnt actor-critic trainer with
    twin Q networks + Polyak soft-update + auto-tuned entropy temperature.
    Pairs with iter 55 ReplayBuffer for sample-efficient continuous control.
  - TD3 (Twin Delayed DDPG): off-policy deterministic actor-critic with
    twin Q + target policy smoothing + delayed actor update. Sibling of
    SAC without entropy regularisation (Fujimoto et al. 2018).

These are kami-native; upstream Isaac Lab uses skrl / rsl_rl / rl_games as
separate packages. The nv_compat surface ships minimal in-tree trainers
(CEM + PPO + SAC + TD3) so that the "training works" loop closes end-to-
end without extra dependencies. Users can still wire skrl / rsl_rl
externally.
"""

from .cem import CEMConfig, CEMResult, CEMTrainer, LinearPolicy
from .ppo import (
    MLP,
    GaussianPolicy,
    PPOConfig,
    PPOResult,
    PPOTrainer,
    ValueFunction,
)
from .sac import QNetwork, SACConfig, SACResult, SACTrainer
from .td3 import DeterministicActor, TD3Config, TD3Result, TD3Trainer

__all__ = [
    "CEMConfig", "CEMResult", "CEMTrainer", "LinearPolicy",
    "PPOConfig", "PPOResult", "PPOTrainer",
    "SACConfig", "SACResult", "SACTrainer", "QNetwork",
    "TD3Config", "TD3Result", "TD3Trainer", "DeterministicActor",
    "MLP", "GaussianPolicy", "ValueFunction",
]
