"""isaaclab.envs.DirectMARLEnv mirror — multi-agent RL env base class.

Third env family alongside ManagerBasedRLEnv (iter 14 + 29) and DirectRLEnv
(iter 30). Where DirectRLEnv has a single agent per env (one obs / one
action / one reward stream), DirectMARLEnv allocates per-agent obs / action
/ reward dicts keyed by agent name — every entry is independent and can
have its own dimensionality:

    cfg = DirectMARLEnvCfg(
        num_envs=4,
        possible_agents=["alice", "bob"],
        num_actions={"alice": 1, "bob": 1},
        num_observations={"alice": 4, "bob": 4},
        num_states=8,                    # centralised critic input (optional)
    )

    class TwoCartpoleMARLEnv(DirectMARLEnv):
        def _setup_scene(self): ...
        def _pre_physics_step(self, actions: dict): ...
        def _apply_action(self): ...
        def _physics_step(self): ...
        def _get_observations(self): return {"alice": [...], "bob": [...]}
        def _get_rewards(self):       return {"alice": [...], "bob": [...]}
        def _get_dones(self):         return {agent: terminated_list},
                                              {agent: truncated_list}
        def _get_states(self): ...                # optional centralised critic
        def _reset_idx(self, env_ids): ...

The base owns:
  - cfg / num_envs / physics_dt / decimation / max_episode_length
  - episode_length_buf  — per-env step counter (shared across agents)
  - _actions             — last action dict {agent: per-env action list-of-lists}
  - extras               — free-form logging dict (per-agent sub-dicts welcomed)
  - auto_reset_done      — when True (default), step() auto-resets envs whose
                            ANY agent reported done

Step pipeline mirrors DirectRLEnv's order (dones BEFORE rewards so
subclasses may apply terminal-state-conditional reward contributions):

    step({agent: actions_per_env}) →
      _pre_physics_step
      for _ in range(decimation):
        _apply_action; _physics_step
      episode_length_buf += 1
      terminated_dict, truncated_dict = _get_dones()
      obs_dict      = _get_observations()
      reward_dict   = _get_rewards()
      if auto_reset_done: reset envs where ANY agent is done; refresh obs
      → (obs_dict, reward_dict, terminated_dict, truncated_dict, info)

`possible_agents` is the canonical list (matches PettingZoo). `agents` is
the active subset (an agent removed mid-episode is still in possible_agents
but absent from `agents`). For symmetric MARL the two are always equal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .direct_rl_env import SimCfg


@dataclass
class DirectMARLEnvCfg:
    """Mirror of isaaclab.envs.DirectMARLEnvCfg."""
    num_envs: int = 1
    possible_agents: List[str] = field(default_factory=lambda: ["agent_0"])
    # Per-agent dimensionalities. Maps each agent name to its int dim.
    num_actions: Dict[str, int] = field(default_factory=lambda: {"agent_0": 1})
    num_observations: Dict[str, int] = field(default_factory=lambda: {"agent_0": 1})
    # Centralised-critic state dim (0 = no shared state / pure decentralised).
    num_states: int = 0
    decimation: int = 2
    episode_length_s: float = 5.0
    sim: SimCfg = field(default_factory=SimCfg)
    seed: Optional[int] = None
    auto_reset_done: bool = True


class DirectMARLEnv:
    """Base class for non-manager-driven multi-agent Isaac Lab env subclasses.

    Owns episode-length tracking + auto-reset of done envs across all agents
    + per-agent action stashing. Subclasses implement the 6 dict-returning
    hooks (`_get_observations` / `_get_rewards` / `_get_dones` / `_reset_idx`
    plus the two action-side hooks `_pre_physics_step` / `_apply_action`).
    """

    def __init__(self, cfg: DirectMARLEnvCfg):
        self.cfg = cfg
        self.num_envs = cfg.num_envs
        self.physics_dt = cfg.sim.dt
        self.decimation = cfg.decimation
        self.max_episode_length = max(1, int(round(cfg.episode_length_s / cfg.sim.dt)))
        self.possible_agents: List[str] = list(cfg.possible_agents)
        self.agents: List[str] = list(cfg.possible_agents)  # active subset
        self.episode_length_buf: List[int] = [0] * cfg.num_envs

        # Per-agent action buffers — each is a list-of-per-env lists.
        self._actions: Dict[str, List[List[float]]] = {
            a: [[0.0] * cfg.num_actions[a] for _ in range(cfg.num_envs)]
            for a in self.possible_agents
        }
        self.extras: Dict[str, Any] = {}
        self._auto_reset = bool(cfg.auto_reset_done)
        # One-shot scene materialisation.
        self._setup_scene()

    # ────────────────────────────────────────────────────────────────────
    # Public Isaac Lab MARL API
    # ────────────────────────────────────────────────────────────────────

    def step(self, actions: Dict[str, List[List[float]]]) -> Tuple[
        Dict[str, List[float]],   # observations
        Dict[str, List[float]],   # rewards
        Dict[str, List[bool]],    # terminated
        Dict[str, List[bool]],    # truncated
        Dict[str, Any],           # info / extras
    ]:
        """One env-level step. Returns the canonical MARL 5-tuple.

        `actions` is a dict keyed by agent name; each value is a list of
        length `num_envs`, each entry a list of `cfg.num_actions[agent]`
        floats. Missing agents default to zero-actions.
        """
        # 1. Stash actions; missing agents → zero-fill (keeps subclass invariants).
        for agent in self.possible_agents:
            if agent in actions:
                a = actions[agent]
                if len(a) != self.num_envs:
                    raise ValueError(
                        f"agent '{agent}' expected {self.num_envs} action vectors; "
                        f"got {len(a)}"
                    )
                self._actions[agent] = [list(v) for v in a]
            else:
                # Zero-fill missing agents.
                dim = self.cfg.num_actions[agent]
                self._actions[agent] = [[0.0] * dim for _ in range(self.num_envs)]

        # 2. Pre-physics hook.
        self._pre_physics_step(self._actions)

        # 3. Inner physics loop at decimation×.
        for _ in range(self.decimation):
            self._apply_action()
            self._physics_step()

        # 4. Per-env episode-length bookkeeping.
        for i in range(self.num_envs):
            self.episode_length_buf[i] += 1

        # 5. Outputs (dones BEFORE rewards per DirectRLEnv convention).
        terminated, truncated = self._get_dones()
        obs = self._get_observations()
        reward = self._get_rewards()

        # 6. Auto-reset envs where ANY agent reported done.
        if self._auto_reset:
            done_ids = []
            for env_idx in range(self.num_envs):
                env_done = False
                for agent in self.possible_agents:
                    t_list = terminated.get(agent, [])
                    tr_list = truncated.get(agent, [])
                    t = t_list[env_idx] if env_idx < len(t_list) else False
                    tr = tr_list[env_idx] if env_idx < len(tr_list) else False
                    if t or tr:
                        env_done = True
                        break
                if env_done:
                    done_ids.append(env_idx)
            if done_ids:
                self._reset_idx(done_ids)
                for i in done_ids:
                    self.episode_length_buf[i] = 0
                # Refresh obs for done envs.
                obs = self._get_observations()

        info = {"extras": dict(self.extras)}
        return obs, reward, terminated, truncated, info

    def reset(self, seed: Optional[int] = None) -> Tuple[
        Dict[str, List[float]], Dict[str, Any],
    ]:
        """Hard reset every env. Returns (obs_dict, info)."""
        if seed is not None:
            self._seed(seed)
        self._reset_idx(list(range(self.num_envs)))
        for i in range(self.num_envs):
            self.episode_length_buf[i] = 0
        return self._get_observations(), {"extras": dict(self.extras)}

    def state(self) -> Optional[List[float]]:
        """Centralised-critic state across all envs (or None if disabled)."""
        if self.cfg.num_states <= 0:
            return None
        return self._get_states()

    def close(self) -> None:
        """Cleanup hook. Default no-op."""
        pass

    # ────────────────────────────────────────────────────────────────────
    # Hooks (subclass overrides)
    # ────────────────────────────────────────────────────────────────────

    def _setup_scene(self) -> None:
        """One-shot scene materialisation. Called from __init__."""
        pass

    def _pre_physics_step(self, actions: Dict[str, List[List[float]]]) -> None:
        """Pre-decimation hook. `actions` is the agent → per-env action dict."""
        pass

    def _apply_action(self) -> None:
        """Per-substep action injection (decimation× per env step)."""
        pass

    def _physics_step(self) -> None:
        """Advance physics by `physics_dt`."""
        pass

    def _get_observations(self) -> Dict[str, List[float]]:
        """Returns {agent: flat obs vector across all envs}."""
        return {a: [] for a in self.possible_agents}

    def _get_rewards(self) -> Dict[str, List[float]]:
        """Returns {agent: per-env scalar reward list}."""
        return {a: [0.0] * self.num_envs for a in self.possible_agents}

    def _get_dones(self) -> Tuple[
        Dict[str, List[bool]], Dict[str, List[bool]],
    ]:
        """Returns ({agent: terminated_list}, {agent: truncated_list})."""
        false = [False] * self.num_envs
        return (
            {a: list(false) for a in self.possible_agents},
            {a: list(false) for a in self.possible_agents},
        )

    def _get_states(self) -> List[float]:
        """Centralised-critic state vector (concat across all agents typically).
        Override when `cfg.num_states > 0`."""
        return [0.0] * self.cfg.num_states

    def _reset_idx(self, env_ids: List[int]) -> None:
        """Per-env reset for environments in `env_ids`."""
        pass

    def _seed(self, seed: int) -> None:
        """Seed any subclass-owned RNGs. Default no-op."""
        pass
