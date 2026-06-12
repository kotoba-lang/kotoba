"""RewardManager — runs RewGroups against env each step.

Mirrors `isaaclab.managers.RewardManager`. Takes a single RewGroup (Isaac Lab
convention: one reward function per env) and exposes:
  - compute(env) → scalar reward
  - get_breakdown(env) → dict of per-term contributions (debug)
  - log_episode_reward() → cumulative reward over an episode
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class RewardManager:
    """Wraps a RewGroup to provide compute() + episode logging."""
    group: Any
    _episode_sum: float = 0.0
    _episode_breakdown: Dict[str, float] = field(default_factory=dict)
    _step_count: int = 0

    def compute(self, env) -> float:
        r = self.group.evaluate(env)
        self._episode_sum += r
        self._step_count += 1
        # Accumulate per-term contributions for episode logging.
        breakdown = self.group.evaluate_breakdown(env)
        for name, val in breakdown.items():
            self._episode_breakdown[name] = self._episode_breakdown.get(name, 0.0) + val
        return r

    def get_breakdown(self, env) -> Dict[str, float]:
        return self.group.evaluate_breakdown(env)

    def log_episode_reward(self) -> Dict[str, float]:
        """Returns cumulative episode metrics: {"total": sum, "<term>": sum, ...}."""
        out = {"total": self._episode_sum, "steps": self._step_count}
        out.update(dict(self._episode_breakdown))
        return out

    def reset_episode_log(self) -> None:
        self._episode_sum = 0.0
        self._episode_breakdown = {}
        self._step_count = 0
