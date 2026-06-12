"""ObservationManager — runs ObsGroups against env each step.

Mirrors `isaaclab.managers.ObservationManager`. Takes a dict of named
ObsGroup configs and exposes `compute(env)` → {group_name: [floats]}.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ObservationManager:
    """Holds a dict of named ObsGroups; compute() returns a dict of vectors.

    Typical usage with Cartpole:
        groups = {"policy": ObsGroup({
            "joint_pos": ObsTerm(mdp.joint_pos_rel),
            "joint_vel": ObsTerm(mdp.joint_vel_rel),
            "last_act":  ObsTerm(mdp.last_action, scale=0.1),
        })}
        obs_mgr = ObservationManager(groups)
        obs_dict = obs_mgr.compute(env)
        # → {"policy": [x, theta, x_dot, theta_dot, 0.1*last_action]}
    """
    groups: Dict[str, Any] = field(default_factory=dict)

    def compute(self, env) -> Dict[str, list]:
        return {name: group.evaluate(env) for name, group in self.groups.items()}

    def get_group(self, name: str):
        return self.groups.get(name)

    def add_group(self, name: str, group) -> "ObservationManager":
        self.groups[name] = group
        return self

    def group_names(self) -> list:
        return list(self.groups.keys())

    def num_groups(self) -> int:
        return len(self.groups)
