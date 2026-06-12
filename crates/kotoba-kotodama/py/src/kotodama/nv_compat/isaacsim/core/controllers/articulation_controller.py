"""isaacsim.core.api.controllers.ArticulationController mirror.

Tracks 40-engine/kami-engine/kami-genesis/src/controllers.rs formula-for-formula:
  - If joint_positions set:  τ_i = kp_i·(q_target_i − q_i) + kd_i·(qdot_target_i − qdot_i) + ff_i
                              (qdot_target defaults to 0 when joint_velocities is None)
  - elif joint_velocities set: τ_i = kd_i·(qdot_target_i − qdot_i) + ff_i
  - else (only joint_efforts set): τ_i = effort_i (direct passthrough)
  - Clamp to ±max_effort_i and route to articulation via apply_action().

stdlib-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ArticulationAction:
    joint_positions: Optional[list] = None
    joint_velocities: Optional[list] = None
    joint_efforts: Optional[list] = None

    @staticmethod
    def positions(targets: list) -> "ArticulationAction":
        return ArticulationAction(joint_positions=list(targets))

    @staticmethod
    def velocities(targets: list) -> "ArticulationAction":
        return ArticulationAction(joint_velocities=list(targets))

    @staticmethod
    def efforts(targets: list) -> "ArticulationAction":
        return ArticulationAction(joint_efforts=list(targets))


class ArticulationController:
    def __init__(self, dof: int, kp: float = 50.0, kd: float = 5.0, max_effort: float = 100.0):
        self.kps: list = [kp] * dof
        self.kds: list = [kd] * dof
        self.max_efforts: list = [max_effort] * dof
        self._last_action: Optional[ArticulationAction] = None
        self._last_torques: list = [0.0] * dof

    def set_gains(self, kps: list, kds: list) -> None:
        assert len(kps) == len(kds) == len(self.kps)
        self.kps = list(kps)
        self.kds = list(kds)

    def set_max_efforts(self, max_efforts: list) -> None:
        assert len(max_efforts) == len(self.max_efforts)
        self.max_efforts = list(max_efforts)

    def get_gains(self):
        return (list(self.kps), list(self.kds))

    def get_max_efforts(self):
        return list(self.max_efforts)

    def get_applied_action(self) -> Optional[ArticulationAction]:
        return self._last_action

    def get_last_torques(self) -> list:
        return list(self._last_torques)

    def apply_action(self, articulation, action: ArticulationAction) -> None:
        """Compute torques from `action` + current joint state, clamp to
        max_efforts, push into the articulation via apply_action({joint_efforts: ...}).

        `articulation` is expected to implement get_joint_positions(),
        get_joint_velocities(), and apply_action({"joint_efforts": [...]}).
        """
        q = articulation.get_joint_positions()
        qdot = articulation.get_joint_velocities()
        dof = len(q)
        assert len(self.kps) == dof
        assert len(self.kds) == dof

        tau = [0.0] * dof

        pos_active = action.joint_positions is not None
        vel_active = action.joint_velocities is not None

        if pos_active:
            assert len(action.joint_positions) == dof
            for i in range(dof):
                tau[i] += self.kps[i] * (action.joint_positions[i] - q[i])

        if vel_active:
            assert len(action.joint_velocities) == dof
            for i in range(dof):
                tau[i] += self.kds[i] * (action.joint_velocities[i] - qdot[i])
        elif pos_active:
            for i in range(dof):
                tau[i] += self.kds[i] * (0.0 - qdot[i])

        if action.joint_efforts is not None:
            assert len(action.joint_efforts) == dof
            for i in range(dof):
                tau[i] += action.joint_efforts[i]

        for i in range(dof):
            lim = self.max_efforts[i]
            if tau[i] > lim:
                tau[i] = lim
            if tau[i] < -lim:
                tau[i] = -lim

        articulation.apply_action({"joint_efforts": tau})
        self._last_action = action
        self._last_torques = tau
