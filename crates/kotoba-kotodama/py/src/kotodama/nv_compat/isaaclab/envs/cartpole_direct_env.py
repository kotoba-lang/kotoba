"""CartpoleDirectEnv — DirectRLEnv reference subclass.

Mirrors `isaaclab_tasks.direct.cartpole.CartpoleEnv` (Isaac Lab 1.x). Same
physics formulas as the manager-driven `ManagerBasedRLEnv` (iter 14), but
expressed via the DirectRLEnv hook contract so subclass-style apps can
ship without ever touching the manager system.

Standard usage:

    env = CartpoleDirectEnv(CartpoleDirectEnvCfg(num_envs=128, urdf_text=URDF))
    obs, info = env.reset(seed=0)
    obs, reward, terminated, truncated, info = env.step([[0.5]] * 128)

Per-env physics state lives in `_states[env_idx]` as a CartpoleState. Reset
randomises the cart x + pole theta by ±0.05 around zero (matches Isaac Lab
defaults).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ..._kernel import (
    ArticulatedSystem,
    CartpoleConfig,
    CartpoleState,
    cartpole_cfg_from_urdf,
    cartpole_step,
    parse_urdf,
)
from .direct_rl_env import DirectRLEnv, DirectRLEnvCfg


# Mirror the LCG used by manager_based_rl_env._Lcg so determinism matches
# across both env families given the same seed.
class _Lcg:
    def __init__(self, seed: int):
        self.state = (seed * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF

    def next_f32_centered(self, half_range: float) -> float:
        self.state = (self.state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        u = ((self.state >> 33) & 0x7FFFFFFF) / float(1 << 31)
        return (u * 2.0 - 1.0) * half_range


@dataclass
class CartpoleDirectEnvCfg(DirectRLEnvCfg):
    """Mirror of isaaclab_tasks.direct.cartpole.CartpoleEnvCfg.

    Inherits DirectRLEnvCfg.num_envs / decimation / episode_length_s / sim.
    Adds reward weights + termination bounds + URDF source.
    """
    num_actions: int = 1
    num_observations: int = 4
    urdf_text: str = ""
    gravity: float = 9.81
    # Reward weights (match nv_compat manager-driven CartpoleEnvCfg defaults).
    alive: float = 1.0
    terminating: float = -2.0
    pole_pos_penalty: float = -1.0
    cart_vel_penalty: float = -0.01
    pole_vel_penalty: float = -0.005
    # Termination bounds.
    pole_bounds: tuple = (-0.2, 0.2)
    cart_bounds: tuple = (-2.4, 2.4)
    # Reset noise.
    reset_noise: float = 0.05


class CartpoleDirectEnv(DirectRLEnv):
    """DirectRLEnv subclass for cartpole — the canonical reference impl.

    Hook implementations:
      - _setup_scene:        parse URDF, build per-env CartpoleConfig+State+RNG
      - _pre_physics_step:   stash latest action (already done by base)
      - _apply_action:       (no-op; force applied inside _physics_step)
      - _physics_step:       cartpole_step per env, force = self._actions[i][0]
      - _get_observations:   {"policy": [[x,xdot,theta,thetadot]]_per_env_flat}
      - _get_rewards:        weighted-sum same as manager_based path
      - _get_dones:          pole_bounds OR cart_bounds OR episode timeout
      - _reset_idx:          zero state + add uniform noise per Lcg
    """

    cfg: CartpoleDirectEnvCfg  # type narrowing

    def _setup_scene(self) -> None:
        cfg: CartpoleDirectEnvCfg = self.cfg  # type: ignore[assignment]
        if not cfg.urdf_text:
            raise ValueError("CartpoleDirectEnvCfg.urdf_text is required")
        self.system: ArticulatedSystem = parse_urdf(cfg.urdf_text)
        self._cartpole_cfg: CartpoleConfig = cartpole_cfg_from_urdf(
            self.system, gravity=cfg.gravity, dt=cfg.sim.dt
        )
        self._states: List[CartpoleState] = [
            CartpoleState() for _ in range(cfg.num_envs)
        ]
        self._rngs: List[_Lcg] = [_Lcg(i) for i in range(cfg.num_envs)]
        # Cached per-env termination flag (set in _get_dones, read in _get_rewards).
        self._last_terminated: List[bool] = [False] * cfg.num_envs

    def _seed(self, seed: int) -> None:
        self._rngs = [_Lcg(seed + i) for i in range(self.num_envs)]

    def _apply_action(self) -> None:
        # Action is applied inside _physics_step (force directly into cartpole_step).
        pass

    def _physics_step(self) -> None:
        for i in range(self.num_envs):
            force = float(self._actions[i][0]) if self._actions[i] else 0.0
            cartpole_step(self._states[i], force, self._cartpole_cfg)

    def _get_observations(self) -> dict:
        # Flat 4-vec per env: [x, x_dot, theta, theta_dot] in env order.
        flat: list = []
        for s in self._states:
            flat.extend([s.x, s.x_dot, s.theta, s.theta_dot])
        return {"policy": flat}

    def _get_rewards(self) -> List[float]:
        cfg: CartpoleDirectEnvCfg = self.cfg  # type: ignore[assignment]
        out: List[float] = []
        for i, s in enumerate(self._states):
            r = (
                cfg.alive
                + (cfg.terminating if self._last_terminated[i] else 0.0)
                + cfg.pole_pos_penalty * s.theta * s.theta
                + cfg.cart_vel_penalty * s.x_dot * s.x_dot
                + cfg.pole_vel_penalty * s.theta_dot * s.theta_dot
            )
            out.append(r)
        return out

    def _get_dones(self) -> tuple:
        cfg: CartpoleDirectEnvCfg = self.cfg  # type: ignore[assignment]
        terminated: List[bool] = []
        truncated: List[bool] = []
        for i, s in enumerate(self._states):
            term = (
                s.theta < cfg.pole_bounds[0]
                or s.theta > cfg.pole_bounds[1]
                or s.x < cfg.cart_bounds[0]
                or s.x > cfg.cart_bounds[1]
            )
            trunc = self.episode_length_buf[i] >= self.max_episode_length
            terminated.append(term)
            truncated.append(trunc)
            self._last_terminated[i] = term
        return terminated, truncated

    def _reset_idx(self, env_ids: List[int]) -> None:
        cfg: CartpoleDirectEnvCfg = self.cfg  # type: ignore[assignment]
        nz = cfg.reset_noise
        for i in env_ids:
            self._states[i] = CartpoleState(
                x=self._rngs[i].next_f32_centered(nz),
                x_dot=self._rngs[i].next_f32_centered(nz),
                theta=self._rngs[i].next_f32_centered(nz),
                theta_dot=self._rngs[i].next_f32_centered(nz),
            )
            self._last_terminated[i] = False
