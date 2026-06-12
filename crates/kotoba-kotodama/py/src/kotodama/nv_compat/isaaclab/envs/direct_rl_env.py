"""isaaclab.envs.DirectRLEnv mirror — non-manager-based env base class.

Parallel pattern to ManagerBasedRLEnv (iter 29). Where ManagerBasedRLEnv
drives the loop via declarative ObsTerm / RewTerm / EventTerm / TerminationTerm
groups, DirectRLEnv lets the subclass implement the step pipeline directly
via 6 hook methods:

    class MyEnv(DirectRLEnv):
        cfg: MyEnvCfg

        def _setup_scene(self): ...               # one-shot scene materialisation
        def _pre_physics_step(self, actions): ... # stash action / clip / decode
        def _apply_action(self): ...              # write action into sim each substep
        def _get_observations(self): ...          # return {"policy": [floats], ...}
        def _get_rewards(self): ...               # return per-env reward list
        def _get_dones(self): ...                 # return (terminated, truncated) lists
        def _reset_idx(self, env_ids): ...        # per-env reset

The base class provides the canonical step / reset loop:

    step(actions) →
      _pre_physics_step
      for _ in range(decimation):
          _apply_action
          _physics_step       # subclass-implemented physics integrator
      episode_length_buf += 1
      obs    = _get_observations()
      reward = _get_rewards()
      terminated, truncated = _get_dones()
      reset_idx(done_envs)    # auto-reset envs whose episode ended
      → (obs, reward, terminated, truncated, info)

    reset(seed) →
      _reset_idx(all envs)
      episode_length_buf = 0
      → (obs, info)

Both pattern families coexist — apps pick whichever matches their author's
mental model. CartpoleDirectEnv (this module) is a working reference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SimCfg:
    """Mirror of isaaclab.sim.SimulationCfg (subset)."""
    dt: float = 1.0 / 120.0
    render_interval: int = 2
    gravity: tuple = (0.0, 0.0, -9.81)


@dataclass
class DirectRLEnvCfg:
    """Mirror of isaaclab.envs.DirectRLEnvCfg.

    Subclasses extend with task-specific fields (action_scale, reward weights,
    termination thresholds, …).
    """
    num_envs: int = 1
    num_actions: int = 1
    num_observations: int = 1
    num_states: int = 0  # for asymmetric actor-critic; 0 = symmetric
    decimation: int = 2
    episode_length_s: float = 5.0
    sim: SimCfg = field(default_factory=SimCfg)
    seed: Optional[int] = None
    # When True, step() auto-resets done envs and rolls the obs to the post-reset
    # state. Matches Isaac Lab default; set to False for "manual reset" workflows.
    auto_reset_done: bool = True


class DirectRLEnv:
    """Base class for non-manager-driven Isaac Lab env subclasses.

    The base owns:
      - cfg / num_envs / physics_dt / decimation
      - episode_length_buf — per-env step counter (auto-zeroed on reset)
      - max_episode_length — cached int from cfg.episode_length_s / cfg.sim.dt
      - _actions — last action vector per env (subclass writes during pre_physics)
      - extras — dict for arbitrary per-env / per-episode logging payloads

    Subclasses implement 6 hooks; sensible no-op defaults let trivial smoke
    tests instantiate the base directly.
    """

    def __init__(self, cfg: DirectRLEnvCfg):
        self.cfg = cfg
        self.num_envs = cfg.num_envs
        self.physics_dt = cfg.sim.dt
        self.decimation = cfg.decimation
        self.max_episode_length = max(1, int(round(cfg.episode_length_s / cfg.sim.dt)))
        self.episode_length_buf: List[int] = [0] * cfg.num_envs
        self._actions: List[List[float]] = [
            [0.0] * cfg.num_actions for _ in range(cfg.num_envs)
        ]
        # Free-form per-env logging payload (mirrors Isaac Lab's `extras` dict).
        # Common usage: extras["log"] = {"reward/alive": ..., "reward/pole_pos": ...}.
        self.extras: Dict[str, Any] = {}
        # Whether to auto-reset done envs at the end of step().
        self._auto_reset = bool(cfg.auto_reset_done)
        # One-shot scene materialisation. Default no-op; subclass overrides.
        self._setup_scene()

    # ────────────────────────────────────────────────────────────────────
    # Public Isaac Lab API
    # ────────────────────────────────────────────────────────────────────

    def step(self, actions: List[List[float]]) -> Tuple[
        Dict[str, list], List[float], List[bool], List[bool], Dict[str, Any]
    ]:
        """One env-level step. Returns Isaac Lab's standard 5-tuple.

        `actions` is a list of length `num_envs`, each a list of length
        `cfg.num_actions`. Single-env subclasses commonly accept a flat list
        and self-wrap; this base preserves the canonical list-of-lists shape.
        """
        if len(actions) != self.num_envs:
            raise ValueError(
                f"expected {self.num_envs} action vectors; got {len(actions)}"
            )
        self._actions = [list(a) for a in actions]

        # 1. Pre-physics hook (subclass clips / decodes / stashes).
        self._pre_physics_step(self._actions)

        # 2. Inner physics loop at decimation×.
        for _ in range(self.decimation):
            self._apply_action()
            self._physics_step()

        # 3. Per-env episode-length bookkeeping.
        for i in range(self.num_envs):
            self.episode_length_buf[i] += 1

        # 4. Outputs. Dones are computed BEFORE rewards so subclasses can
        # apply terminal-state-conditional reward contributions
        # (mirrors isaaclab.envs.DirectRLEnv where `_get_rewards()` reads
        # `self.reset_terminated` populated by `_get_dones()` in subclasses
        # that use the convention).
        terminated, truncated = self._get_dones()
        obs = self._get_observations()
        reward = self._get_rewards()

        # 5. Auto-reset envs whose episode just ended.
        if self._auto_reset:
            done_ids = [
                i for i in range(self.num_envs)
                if (i < len(terminated) and terminated[i])
                or (i < len(truncated) and truncated[i])
            ]
            if done_ids:
                self._reset_idx(done_ids)
                for i in done_ids:
                    self.episode_length_buf[i] = 0
                # Refresh obs to reflect the post-reset state for done envs.
                obs = self._get_observations()

        info = {"extras": dict(self.extras)}
        return obs, reward, terminated, truncated, info

    def reset(self, seed: Optional[int] = None) -> Tuple[Dict[str, list], Dict[str, Any]]:
        """Hard reset every env. Returns (obs, info)."""
        if seed is not None:
            self._seed(seed)
        self._reset_idx(list(range(self.num_envs)))
        for i in range(self.num_envs):
            self.episode_length_buf[i] = 0
        return self._get_observations(), {"extras": dict(self.extras)}

    def close(self) -> None:
        """Cleanup hook (releases sim resources). Default no-op."""
        pass

    # ────────────────────────────────────────────────────────────────────
    # Hooks (subclass overrides)
    # ────────────────────────────────────────────────────────────────────

    def _setup_scene(self) -> None:
        """One-shot scene materialisation. Called from __init__."""
        pass

    def _pre_physics_step(self, actions: List[List[float]]) -> None:
        """Pre-decimation hook. Subclass clips actions, decodes commands, etc."""
        pass

    def _apply_action(self) -> None:
        """Per-substep action injection (called decimation× per env step)."""
        pass

    def _physics_step(self) -> None:
        """Advance physics by `physics_dt`. Subclass implements the integrator."""
        pass

    def _get_observations(self) -> Dict[str, list]:
        """Returns observations dict. Defaults to {"policy": []}."""
        return {"policy": []}

    def _get_rewards(self) -> List[float]:
        """Returns per-env scalar rewards."""
        return [0.0] * self.num_envs

    def _get_dones(self) -> Tuple[List[bool], List[bool]]:
        """Returns (terminated, truncated) per env."""
        f = [False] * self.num_envs
        return f, list(f)

    def _reset_idx(self, env_ids: List[int]) -> None:
        """Per-env reset (zeros state for env indices in `env_ids`)."""
        pass

    def _seed(self, seed: int) -> None:
        """Seed any subclass-owned RNGs. Default no-op."""
        pass
