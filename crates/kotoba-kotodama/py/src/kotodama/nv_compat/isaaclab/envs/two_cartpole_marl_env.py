"""TwoCartpoleMARLEnv — DirectMARLEnv reference subclass.

Two independent cartpoles per env, two agents. Each agent observes its own
cartpole + applies its own cart force. Reward is cooperative-ish: each
agent's reward = own_alive + small partner_alive bonus (so agents have a
weak coupling without sharing physics).

This is the smallest realistic MARL scene that exercises the dict-based
contract. Demonstrates the canonical pattern:

    cfg = TwoCartpoleMARLEnvCfg(num_envs=4, urdf_text=URDF)
    env = TwoCartpoleMARLEnv(cfg)
    obs, info = env.reset(seed=0)
    # obs = {"alice": [4 × num_envs floats], "bob": [4 × num_envs floats]}
    actions = {
        "alice": [[0.0]] * cfg.num_envs,
        "bob":   [[0.0]] * cfg.num_envs,
    }
    obs, reward, term, trunc, info = env.step(actions)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from ..._kernel import (
    ArticulatedSystem,
    CartpoleConfig,
    CartpoleState,
    cartpole_cfg_from_urdf,
    cartpole_step,
    parse_urdf,
)
from .cartpole_direct_env import _Lcg
from .direct_marl_env import DirectMARLEnv, DirectMARLEnvCfg
from .direct_rl_env import SimCfg


@dataclass
class TwoCartpoleMARLEnvCfg(DirectMARLEnvCfg):
    """Two-cartpole MARL config. Each agent gets one cartpole."""
    urdf_text: str = ""
    gravity: float = 9.81
    # Per-agent reward weights.
    alive: float = 1.0
    terminating: float = -2.0
    pole_pos_penalty: float = -1.0
    cart_vel_penalty: float = -0.01
    pole_vel_penalty: float = -0.005
    # Cross-agent cooperation bonus — fraction of partner's alive reward.
    partner_bonus: float = 0.1
    # Termination bounds.
    pole_bounds: tuple = (-0.2, 0.2)
    cart_bounds: tuple = (-2.4, 2.4)
    reset_noise: float = 0.05

    # Override the parent defaults to encode the 2-agent layout up-front so
    # `TwoCartpoleMARLEnvCfg(num_envs=N, urdf_text=URDF)` "just works".
    possible_agents: List[str] = field(
        default_factory=lambda: ["alice", "bob"]
    )
    num_actions: Dict[str, int] = field(
        default_factory=lambda: {"alice": 1, "bob": 1}
    )
    num_observations: Dict[str, int] = field(
        default_factory=lambda: {"alice": 4, "bob": 4}
    )
    # Centralised state = concat(alice_obs, bob_obs) = 8 floats per env.
    num_states: int = 8


class TwoCartpoleMARLEnv(DirectMARLEnv):
    """Reference DirectMARLEnv subclass with 2 cartpoles + 2 agents.

    Per-env state: `_states[agent][env_idx]` → CartpoleState.
    Per-env termination flag: `_terminated[agent][env_idx]` (cached during
    _get_dones, read by _get_rewards on the same step thanks to the
    DirectRLEnv-convention "dones before rewards" pipeline order).
    """

    cfg: TwoCartpoleMARLEnvCfg  # type narrowing

    def _setup_scene(self) -> None:
        cfg: TwoCartpoleMARLEnvCfg = self.cfg  # type: ignore[assignment]
        if not cfg.urdf_text:
            raise ValueError("TwoCartpoleMARLEnvCfg.urdf_text is required")
        self.system: ArticulatedSystem = parse_urdf(cfg.urdf_text)
        self._cartpole_cfg: CartpoleConfig = cartpole_cfg_from_urdf(
            self.system, gravity=cfg.gravity, dt=cfg.sim.dt
        )
        # Per-agent per-env state + per-agent per-env LCG.
        self._states: Dict[str, List[CartpoleState]] = {
            agent: [CartpoleState() for _ in range(cfg.num_envs)]
            for agent in self.possible_agents
        }
        # Offset LCG seeds per agent so agents reset to different states.
        self._rngs: Dict[str, List[_Lcg]] = {
            agent: [_Lcg((a_idx + 1) * 1000 + i) for i in range(cfg.num_envs)]
            for a_idx, agent in enumerate(self.possible_agents)
        }
        self._terminated: Dict[str, List[bool]] = {
            agent: [False] * cfg.num_envs for agent in self.possible_agents
        }

    def _seed(self, seed: int) -> None:
        for a_idx, agent in enumerate(self.possible_agents):
            self._rngs[agent] = [
                _Lcg(seed + (a_idx + 1) * 1000 + i)
                for i in range(self.num_envs)
            ]

    def _apply_action(self) -> None:
        # Action injected inside _physics_step (force read from self._actions).
        pass

    def _physics_step(self) -> None:
        for agent in self.possible_agents:
            for env_idx in range(self.num_envs):
                action_vec = self._actions[agent][env_idx]
                force = float(action_vec[0]) if action_vec else 0.0
                cartpole_step(
                    self._states[agent][env_idx], force, self._cartpole_cfg
                )

    def _get_observations(self) -> Dict[str, List[float]]:
        out: Dict[str, List[float]] = {}
        for agent in self.possible_agents:
            flat: List[float] = []
            for s in self._states[agent]:
                flat.extend([s.x, s.x_dot, s.theta, s.theta_dot])
            out[agent] = flat
        return out

    def _get_states(self) -> List[float]:
        """Centralised state per env = concat(alice obs, bob obs) for env 0
        only (returns 8 floats matching cfg.num_states). MARL critics that
        want per-env state should call `_get_observations()` and stitch."""
        obs = self._get_observations()
        if self.num_envs == 0:
            return [0.0] * self.cfg.num_states
        out: List[float] = []
        for agent in self.possible_agents:
            agent_obs = obs[agent]
            obs_dim = self.cfg.num_observations[agent]
            out.extend(agent_obs[:obs_dim])
        return out

    def _get_rewards(self) -> Dict[str, List[float]]:
        cfg: TwoCartpoleMARLEnvCfg = self.cfg  # type: ignore[assignment]
        # Per-agent alive reward + cross-agent bonus.
        out: Dict[str, List[float]] = {a: [0.0] * self.num_envs
                                       for a in self.possible_agents}
        for env_idx in range(self.num_envs):
            for agent in self.possible_agents:
                s = self._states[agent][env_idx]
                own_alive = 0.0 if self._terminated[agent][env_idx] else cfg.alive
                own_reward = (
                    own_alive
                    + (cfg.terminating if self._terminated[agent][env_idx] else 0.0)
                    + cfg.pole_pos_penalty * s.theta * s.theta
                    + cfg.cart_vel_penalty * s.x_dot * s.x_dot
                    + cfg.pole_vel_penalty * s.theta_dot * s.theta_dot
                )
                # Cooperation bonus = partner_bonus * partner's alive flag.
                partner_bonus = 0.0
                for other in self.possible_agents:
                    if other == agent:
                        continue
                    if not self._terminated[other][env_idx]:
                        partner_bonus += cfg.partner_bonus * cfg.alive
                out[agent][env_idx] = own_reward + partner_bonus
        return out

    def _get_dones(self) -> tuple:
        cfg: TwoCartpoleMARLEnvCfg = self.cfg  # type: ignore[assignment]
        terminated: Dict[str, List[bool]] = {}
        truncated: Dict[str, List[bool]] = {}
        for agent in self.possible_agents:
            term_list: List[bool] = []
            trunc_list: List[bool] = []
            for env_idx in range(self.num_envs):
                s = self._states[agent][env_idx]
                term = (
                    s.theta < cfg.pole_bounds[0]
                    or s.theta > cfg.pole_bounds[1]
                    or s.x < cfg.cart_bounds[0]
                    or s.x > cfg.cart_bounds[1]
                )
                trunc = self.episode_length_buf[env_idx] >= self.max_episode_length
                term_list.append(term)
                trunc_list.append(trunc)
                self._terminated[agent][env_idx] = term
            terminated[agent] = term_list
            truncated[agent] = trunc_list
        return terminated, truncated

    def _reset_idx(self, env_ids: List[int]) -> None:
        cfg: TwoCartpoleMARLEnvCfg = self.cfg  # type: ignore[assignment]
        nz = cfg.reset_noise
        for env_idx in env_ids:
            for agent in self.possible_agents:
                rng = self._rngs[agent][env_idx]
                self._states[agent][env_idx] = CartpoleState(
                    x=rng.next_f32_centered(nz),
                    x_dot=rng.next_f32_centered(nz),
                    theta=rng.next_f32_centered(nz),
                    theta_dot=rng.next_f32_centered(nz),
                )
                self._terminated[agent][env_idx] = False
