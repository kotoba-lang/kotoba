"""isaaclab.managers — runtime layer that drives iter 22 term builders.

Mirrors `isaaclab.managers` (Isaac Lab 1.x). Wraps the declarative
ObsTerm / RewTerm / EventTerm / TerminationTerm groups (iter 22 mdp builders)
into managers that the env automatically calls each step:

  - ObservationManager  — compute() returns a dict of per-group obs vectors
  - RewardManager       — compute() returns scalar reward + breakdown
  - EventManager        — apply(mode) fires events ("reset"/"interval"/"startup")
  - TerminationManager  — compute() returns (terminated, info)

ManagerBasedRLEnv (iter 14) gets an optional `managers={...}` ctor argument
that, when supplied, replaces the hardcoded step_all reward/termination
computation with manager-driven evaluation.
"""

from .event_manager import EventManager
from .observation_manager import ObservationManager
from .reward_manager import RewardManager
from .termination_manager import TerminationManager, TerminationTerm

__all__ = [
    "ObservationManager", "RewardManager", "EventManager",
    "TerminationManager", "TerminationTerm",
]
