"""isaaclab.envs.ManagerBasedRLEnv mirror.

R1.1 scope: CartpoleEnvCfg (mirrors isaaclab_tasks.manager_based.classic.cartpole
.CartpoleEnvCfg) + ManagerBasedRLEnv wrapper. Multi-env vectorization arrives
in R1.5 via kami-genesis WGSL compute (Phase D).

Manager-driven RL loop (iter 29): the constructor optionally takes
`observations_cfg / rewards_cfg / events_cfg / terminations_cfg`; each may be
a pre-built manager (ObservationManager / RewardManager / EventManager /
TerminationManager) OR raw group config (ObsGroup dict / RewGroup / EventTerm
dict / TerminationTerm dict) — raw configs are auto-wrapped into the
matching manager. When managers are installed, `reset_managed(seed)` /
`step_managed(action)` drive the Isaac Lab standard declarative loop:

    env = ManagerBasedRLEnv(
        cfg=cartpole_cfg,
        observations_cfg={"policy": ObsGroup({"pos": ObsTerm(mdp.joint_pos_rel)})},
        rewards_cfg=RewGroup({"alive": RewTerm(mdp.is_alive)}),
        events_cfg={"reset_pose": EventTerm(mdp.reset_joints_by_offset, mode="reset")},
        terminations_cfg={"timeout": TerminationTerm(mdp.time_out, time_out=True)},
    )
    obs = env.reset_managed(seed=0)
    out = env.step_managed([0.5])  # {observations, reward, terminated, truncated, info}

The existing `step(action) / reset() / step_all(actions)` API is preserved
unchanged when no managers are installed — managers are strictly additive.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

from ..._kernel import (
    ArticulatedSystem,
    CartpoleConfig,
    CartpoleState,
    cartpole_cfg_from_urdf,
    cartpole_step,
    parse_urdf,
)
from ..managers import (
    EventManager,
    ObservationManager,
    RewardManager,
    TerminationManager,
)


# Mirror Lcg seeded RNG with kami_shugyo::cartpole_env::Lcg.
class _Lcg:
    def __init__(self, seed: int):
        self.state = (seed * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF

    def next_f32_centered(self, half_range: float) -> float:
        self.state = (self.state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        u = ((self.state >> 33) & 0x7FFFFFFF) / float(1 << 31)
        return (u * 2.0 - 1.0) * half_range


@dataclass
class CartpoleEnvCfg:
    """Mirror of isaaclab_tasks.manager_based.classic.cartpole.CartpoleEnvCfg.

    Loaded directly from 40-engine/kami-engine/fixtures/cartpole/scene.yaml or set
    programmatically.
    """
    num_envs: int = 1                  # R1.1 = 1 env; R1.5 vectorizes via WGSL
    physics_dt: float = 1.0 / 60.0
    decimation: int = 2
    gravity: float = 9.81
    urdf_text: str = ""

    # reward weights (match scene.yaml)
    alive: float = 1.0
    terminating: float = -2.0
    pole_pos_penalty: float = -1.0
    cart_vel_penalty: float = -0.01
    pole_vel_penalty: float = -0.005

    # termination
    max_episode_length_s: float = 5.0
    pole_bounds: tuple[float, float] = (-0.2, 0.2)
    cart_bounds: tuple[float, float] = (-2.4, 2.4)


class ManagerBasedRLEnv:
    """Mirror of isaaclab.envs.ManagerBasedRLEnv (Cartpole-only at R1.1).

    Supports vectorized envs via `cfg.num_envs > 1`. When num_envs == 1 the
    behavior matches the single-env path; for num_envs > 1, internal state
    is held as parallel lists and stepped in lockstep via per-env Cartpole
    integration (mirrors kami-shugyo::VectorizedCartpoleEnv).
    """

    def __init__(
        self,
        cfg: CartpoleEnvCfg,
        system: Optional[ArticulatedSystem] = None,
        observations_cfg: Any = None,
        rewards_cfg: Any = None,
        events_cfg: Any = None,
        terminations_cfg: Any = None,
    ):
        self.cfg = cfg
        if system is None:
            if not cfg.urdf_text:
                raise ValueError("provide system or cfg.urdf_text")
            system = parse_urdf(cfg.urdf_text)
        self.system = system
        self._cartpole_cfg: CartpoleConfig = cartpole_cfg_from_urdf(
            system, gravity=cfg.gravity, dt=cfg.physics_dt
        )
        self._max_steps = int(round(cfg.max_episode_length_s / cfg.physics_dt))
        self._steps = 0
        self._rng = _Lcg(0)
        # Vectorized state (always allocated; for num_envs==1 this is just one entry).
        n = max(1, cfg.num_envs)
        self._states_v: list = [CartpoleState() for _ in range(n)]
        self._steps_v: list = [0] * n
        self._rngs_v: list = [_Lcg(i) for i in range(n)]
        # Per-env physics configs (sim2real DR). None = shared cfg path.
        self._per_env_cfgs: Optional[list] = None
        # Back-compat: keep _state alias for num_envs==1 single-env path.
        self._state = self._states_v[0]

        # Manager-driven loop wiring (iter 29). Each is None when not used.
        # Last-action / terminated flags read by mdp.last_action / is_alive /
        # is_terminated reward functions.
        self._last_action: list = [0.0]
        self._terminated: bool = False
        self._truncated: bool = False
        self._commands: dict = {}
        self._obs_mgr: Optional[ObservationManager] = _coerce_observation_manager(
            observations_cfg
        )
        self._reward_mgr: Optional[RewardManager] = _coerce_reward_manager(rewards_cfg)
        self._event_mgr: Optional[EventManager] = _coerce_event_manager(events_cfg)
        self._termination_mgr: Optional[TerminationManager] = (
            _coerce_termination_manager(terminations_cfg)
        )
        # Fire startup events once (e.g. one-shot physics randomisation).
        if self._event_mgr is not None:
            self._event_mgr.apply(self, mode="startup")

    # ----- public manager accessors -----

    @property
    def observation_manager(self) -> Optional[ObservationManager]:
        return self._obs_mgr

    @property
    def reward_manager(self) -> Optional[RewardManager]:
        return self._reward_mgr

    @property
    def event_manager(self) -> Optional[EventManager]:
        return self._event_mgr

    @property
    def termination_manager(self) -> Optional[TerminationManager]:
        return self._termination_mgr

    def is_manager_driven(self) -> bool:
        """True when at least one manager is installed (manager loop is wired)."""
        return any(
            m is not None
            for m in (self._obs_mgr, self._reward_mgr, self._event_mgr, self._termination_mgr)
        )

    @property
    def num_envs(self) -> int:
        return self.cfg.num_envs

    @property
    def observation_space(self) -> dict:
        return {"shape": (4,), "low": -math.inf, "high": math.inf}

    @property
    def action_space(self) -> dict:
        return {"shape": (1,), "low": -self._cartpole_cfg.force_mag,
                "high": self._cartpole_cfg.force_mag}

    def reset(self, seed: Optional[int] = None) -> tuple[list[float], dict]:
        if seed is not None:
            self._rng = _Lcg(seed)
        self._state = CartpoleState(
            x=self._rng.next_f32_centered(0.05),
            x_dot=self._rng.next_f32_centered(0.05),
            theta=self._rng.next_f32_centered(0.05),
            theta_dot=self._rng.next_f32_centered(0.05),
        )
        self._states_v[0] = self._state
        self._steps = 0
        self._steps_v[0] = 0
        return self._obs(), {}

    def reset_all(self, base_seed: Optional[int] = None) -> list:
        """Vectorized reset (num_envs > 1). Returns observations as a list of
        per-env [x, x_dot, theta, theta_dot] arrays."""
        if base_seed is not None:
            self._rngs_v = [_Lcg(base_seed + i) for i in range(self.num_envs)]
        out = []
        for i in range(self.num_envs):
            self._states_v[i] = CartpoleState(
                x=self._rngs_v[i].next_f32_centered(0.05),
                x_dot=self._rngs_v[i].next_f32_centered(0.05),
                theta=self._rngs_v[i].next_f32_centered(0.05),
                theta_dot=self._rngs_v[i].next_f32_centered(0.05),
            )
            self._steps_v[i] = 0
            s = self._states_v[i]
            out.append([s.x, s.x_dot, s.theta, s.theta_dot])
        self._state = self._states_v[0]
        return out

    def set_per_env_cfgs(self, cfgs: list) -> None:
        """Install per-env physics configs (sim2real domain randomisation).

        `cfgs` must be a list of length num_envs, each element a CartpoleConfig
        (duck-typed: needs `cart_mass`, `pole_mass`, `pole_half_length`,
        `gravity`, `force_mag`, `dt`). When installed, step_all() dispatches
        each env against its own cfg. Mirrors
        kami_shugyo::VectorizedCartpoleEnv::set_per_env_configs.
        """
        assert len(cfgs) == self.num_envs
        self._per_env_cfgs = list(cfgs)

    def clear_per_env_cfgs(self) -> None:
        """Drop per-env DR; subsequent step_all() reverts to shared cfg."""
        self._per_env_cfgs = None

    def per_env_cfgs(self):
        """Access the installed per-env cfgs (or None)."""
        return self._per_env_cfgs

    def step_all(self, actions: list) -> list:
        """Vectorized step. `actions` is a list of length num_envs; returns
        a list of dicts {observation, reward, terminated, truncated} per env.

        Per-env physics configs (sim2real DR) honoured when installed via
        set_per_env_cfgs(); otherwise shared `_cartpole_cfg` applies to all.
        """
        assert len(actions) == self.num_envs
        out = []
        c = self.cfg
        for i in range(self.num_envs):
            cfg_i = (
                self._per_env_cfgs[i]
                if self._per_env_cfgs is not None
                else self._cartpole_cfg
            )
            for _ in range(self.cfg.decimation):
                cartpole_step(self._states_v[i], float(actions[i]), cfg_i)
            self._steps_v[i] += self.cfg.decimation
            s = self._states_v[i]
            terminated = (
                s.theta < c.pole_bounds[0] or s.theta > c.pole_bounds[1]
                or s.x < c.cart_bounds[0] or s.x > c.cart_bounds[1]
            )
            truncated = self._steps_v[i] >= self._max_steps
            reward = (
                c.alive
                + (c.terminating if terminated else 0.0)
                + c.pole_pos_penalty * s.theta * s.theta
                + c.cart_vel_penalty * s.x_dot * s.x_dot
                + c.pole_vel_penalty * s.theta_dot * s.theta_dot
            )
            out.append({
                "observation": [s.x, s.x_dot, s.theta, s.theta_dot],
                "reward": reward,
                "terminated": terminated,
                "truncated": truncated,
            })
        # Back-compat alias to first env.
        self._state = self._states_v[0]
        return out

    def step(self, action: list[float]) -> tuple[list[float], float, bool, bool, dict]:
        for _ in range(self.cfg.decimation):
            cartpole_step(self._state, float(action[0]), self._cartpole_cfg)
        self._steps += self.cfg.decimation

        terminated = (
            self._state.theta < self.cfg.pole_bounds[0]
            or self._state.theta > self.cfg.pole_bounds[1]
            or self._state.x < self.cfg.cart_bounds[0]
            or self._state.x > self.cfg.cart_bounds[1]
        )
        truncated = self._steps >= self._max_steps

        c = self.cfg
        reward = (
            c.alive
            + (c.terminating if terminated else 0.0)
            + c.pole_pos_penalty * self._state.theta * self._state.theta
            + c.cart_vel_penalty * self._state.x_dot * self._state.x_dot
            + c.pole_vel_penalty * self._state.theta_dot * self._state.theta_dot
        )
        return self._obs(), reward, terminated, truncated, {}

    def _obs(self) -> list[float]:
        return [self._state.x, self._state.x_dot, self._state.theta, self._state.theta_dot]

    # ----- env accessors used by mdp term functions -----

    def get_joint_positions(self) -> list[float]:
        """Cart x + pole theta — read by mdp.joint_pos_rel."""
        return [self._state.x, self._state.theta]

    def get_joint_velocities(self) -> list[float]:
        """Cart x_dot + pole theta_dot — read by mdp.joint_vel_rel."""
        return [self._state.x_dot, self._state.theta_dot]

    def set_joint_positions(self, positions: list[float]) -> None:
        if len(positions) >= 1:
            self._state.x = float(positions[0])
        if len(positions) >= 2:
            self._state.theta = float(positions[1])

    def set_joint_velocities(self, velocities: list[float]) -> None:
        if len(velocities) >= 1:
            self._state.x_dot = float(velocities[0])
        if len(velocities) >= 2:
            self._state.theta_dot = float(velocities[1])

    # ----- manager-driven loop (iter 29) -----

    def reset_managed(self, seed: Optional[int] = None) -> dict:
        """Reset state + fire reset-mode events + return manager observations.

        Mirrors `isaaclab.envs.ManagerBasedRLEnv.reset()` declarative behavior.
        Calls `reset()` first (existing single-env path), then fires
        EventManager.apply("reset"), resets EventManager step counter, clears
        RewardManager episode log, and returns the ObservationManager dict.

        Returns: `{group_name: [obs_floats], ...}` — empty dict if no obs_mgr.
        """
        # Re-seed env._rng + clear cartpole state via the existing reset() path.
        self.reset(seed=seed)
        # Re-arm manager-driven episode bookkeeping.
        self._terminated = False
        self._truncated = False
        self._last_action = [0.0]
        if self._event_mgr is not None:
            self._event_mgr.reset()
            self._event_mgr.apply(self, mode="reset")
        if self._reward_mgr is not None:
            self._reward_mgr.reset_episode_log()
        if self._obs_mgr is not None:
            return self._obs_mgr.compute(self)
        return {}

    def step_managed(self, action: list[float]) -> dict:
        """Manager-driven step. Mirrors Isaac Lab `ManagerBasedRLEnv.step()`.

        Pipeline (each manager skipped if not installed):
          1. Stash `action` on env._last_action for mdp.last_action / action_l2
          2. Advance physics (decimation cartpole_steps from existing single-env path)
          3. Increment EventManager step counter + apply("interval")
          4. TerminationManager.compute() → set env._terminated / _truncated
             (fallback to built-in cartpole bounds + max_steps when no mgr)
          5. RewardManager.compute(env) (accumulates episode log)
          6. ObservationManager.compute(env)

        Returns a dict matching Isaac Lab convention:
          {
            "observations": {group_name: [floats], ...},  # empty if no obs_mgr
            "reward":       float,                          # 0.0 if no reward_mgr
            "terminated":   bool,
            "truncated":    bool,
            "info":         {"termination": {term_name: bool, ...}},
          }
        """
        # 1. Stash action.
        self._last_action = list(action)

        # 2. Physics (re-use existing single-env decimation loop).
        for _ in range(self.cfg.decimation):
            cartpole_step(self._state, float(action[0]), self._cartpole_cfg)
        self._steps += self.cfg.decimation
        # Keep vectorized aliases in sync (some manager terms may read _states_v[0]).
        self._states_v[0] = self._state
        self._steps_v[0] = self._steps

        # 3. EventManager interval-mode terms.
        if self._event_mgr is not None:
            self._event_mgr.step()
            self._event_mgr.apply(self, mode="interval")

        # 4. Termination — manager wins if installed; else fall back to cfg bounds.
        info: dict = {}
        if self._termination_mgr is not None:
            terminated, truncated, term_info = self._termination_mgr.compute(self)
            info["termination"] = term_info
        else:
            terminated = (
                self._state.theta < self.cfg.pole_bounds[0]
                or self._state.theta > self.cfg.pole_bounds[1]
                or self._state.x < self.cfg.cart_bounds[0]
                or self._state.x > self.cfg.cart_bounds[1]
            )
            truncated = self._steps >= self._max_steps
        self._terminated = terminated
        self._truncated = truncated

        # 5. Reward.
        if self._reward_mgr is not None:
            reward = self._reward_mgr.compute(self)
        else:
            c = self.cfg
            reward = (
                c.alive
                + (c.terminating if terminated else 0.0)
                + c.pole_pos_penalty * self._state.theta * self._state.theta
                + c.cart_vel_penalty * self._state.x_dot * self._state.x_dot
                + c.pole_vel_penalty * self._state.theta_dot * self._state.theta_dot
            )

        # 6. Observations.
        observations: dict = (
            self._obs_mgr.compute(self) if self._obs_mgr is not None else {}
        )

        return {
            "observations": observations,
            "reward": float(reward),
            "terminated": bool(terminated),
            "truncated": bool(truncated),
            "info": info,
        }


# ----- manager coercion helpers (raw cfg → manager instance) -----

def _coerce_observation_manager(cfg: Any) -> Optional[ObservationManager]:
    """Accepts ObservationManager / dict[str, ObsGroup] / None."""
    if cfg is None:
        return None
    if isinstance(cfg, ObservationManager):
        return cfg
    if isinstance(cfg, dict):
        return ObservationManager(groups=dict(cfg))
    raise TypeError(
        f"observations_cfg must be ObservationManager or dict[str, ObsGroup]; got {type(cfg).__name__}"
    )


def _coerce_reward_manager(cfg: Any) -> Optional[RewardManager]:
    """Accepts RewardManager / RewGroup / None."""
    if cfg is None:
        return None
    if isinstance(cfg, RewardManager):
        return cfg
    # Anything with `.evaluate(env)` + `.evaluate_breakdown(env)` is a RewGroup.
    if hasattr(cfg, "evaluate") and hasattr(cfg, "evaluate_breakdown"):
        return RewardManager(group=cfg)
    raise TypeError(
        f"rewards_cfg must be RewardManager or RewGroup; got {type(cfg).__name__}"
    )


def _coerce_event_manager(cfg: Any) -> Optional[EventManager]:
    """Accepts EventManager / dict[str, EventTerm] / None."""
    if cfg is None:
        return None
    if isinstance(cfg, EventManager):
        return cfg
    if isinstance(cfg, dict):
        return EventManager(terms=dict(cfg))
    raise TypeError(
        f"events_cfg must be EventManager or dict[str, EventTerm]; got {type(cfg).__name__}"
    )


def _coerce_termination_manager(cfg: Any) -> Optional[TerminationManager]:
    """Accepts TerminationManager / dict[str, TerminationTerm] / None."""
    if cfg is None:
        return None
    if isinstance(cfg, TerminationManager):
        return cfg
    if isinstance(cfg, dict):
        return TerminationManager(terms=dict(cfg))
    raise TypeError(
        f"terminations_cfg must be TerminationManager or dict[str, TerminationTerm]; got {type(cfg).__name__}"
    )
