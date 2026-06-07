"""Curriculum-learning manager — gradual task-difficulty progression.

Mirror of `isaaclab.envs.mdp.curriculums` (Isaac Lab 1.x). Used in every
quadruped locomotion task to progressively increase terrain difficulty
+ reward weight + action scale as the policy gets better. Each
CurriculumTerm is a function that monitors a metric (e.g. episode
distance, average reward) and mutates env state when a threshold is hit.

Surface:
  - CurriculumTerm     — dataclass: func + params + name + tracking
  - CurriculumManager  — registry of terms; compute(env) fires every
                          term in registration order
  - 3 standard fns:
        terrain_levels_vy(env, distance_threshold, ...)
            — advance terrain curriculum when env moves further than
              threshold (Isaac Lab's anymal_c standard)
        modify_reward_weight(env, term_name, weight, num_steps)
            — linear ramp of a RewTerm weight over num_steps
        modify_action_scale(env, scale, num_steps)
            — linear ramp of action scale (e.g. progressive action
              authority during early training)

Each function is permissive: when env lacks the required state (e.g. no
terrain_importer attribute), the term is a silent no-op so cfg files
can be reused across envs that don't need every curriculum.

Pure stdlib. Composes with iter 44 TerrainImporter (.update_env_origins)
and iter 22 mdp.RewardManager (.group.terms for weight modification).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ────────────────────────────────────────────────────────────────────────────
# CurriculumTerm + CurriculumManager
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class CurriculumTerm:
    """One curriculum term. `func(env, env_ids, **params) -> dict` mutates
    env state and returns a stats dict for logging.

    `env_ids` is the subset of envs to consider (default: all). Useful
    for per-env curriculum (env i can be at a higher level than env j).
    """
    func: Callable
    params: Dict[str, Any] = field(default_factory=dict)
    name: str = ""

    def evaluate(self, env: Any, env_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        if env_ids is None:
            n = getattr(env, "num_envs", 1)
            env_ids = list(range(n))
        result = self.func(env, env_ids, **self.params)
        return result if isinstance(result, dict) else {}


class CurriculumManager:
    """Composes multiple CurriculumTerm. compute(env) fires every term
    in registration order and merges their stats dicts.

    Standard usage:

        cm = CurriculumManager(terms={
            "terrain_levels": CurriculumTerm(
                func=mdp.terrain_levels_vy,
                params={"distance_threshold": 6.0, "asset_name": "robot"},
            ),
            "reward_ramp": CurriculumTerm(
                func=mdp.modify_reward_weight,
                params={"term_name": "track_lin_vel", "weight": 1.0,
                         "num_steps": 50_000},
            ),
        })
        # In env.step():
        cm.compute(env)
    """

    def __init__(self, terms: Optional[Dict[str, CurriculumTerm]] = None):
        self.terms: Dict[str, CurriculumTerm] = dict(terms) if terms else {}

    def compute(self, env: Any,
                env_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """Fire every term; merge stats dicts keyed by term name."""
        out: Dict[str, Any] = {}
        for name, term in self.terms.items():
            stats = term.evaluate(env, env_ids)
            if stats:
                out[name] = stats
        return out

    def add_term(self, name: str, term: CurriculumTerm) -> "CurriculumManager":
        self.terms[name] = term
        return self

    def remove_term(self, name: str) -> bool:
        return self.terms.pop(name, None) is not None

    def num_terms(self) -> int:
        return len(self.terms)

    def term_names(self) -> List[str]:
        return list(self.terms.keys())


# ────────────────────────────────────────────────────────────────────────────
# Standard curriculum functions
# ────────────────────────────────────────────────────────────────────────────


def terrain_levels_vy(
    env: Any,
    env_ids: List[int],
    distance_threshold: float = 6.0,
    asset_name: str = "robot",
    advance_on_success: bool = True,
    regress_on_failure: bool = True,
    failure_threshold: float = 1.0,
) -> Dict[str, Any]:
    """Advance/regress terrain curriculum based on per-env locomotion distance.

    Reads `env.terrain_importer` (iter 44) for level-advance API; reads
    `env._curriculum_state` for per-env episode-distance accumulator.
    Bumps terrain_level by +1 when distance ≥ distance_threshold
    (advance_on_success), -1 when < failure_threshold (regress_on_failure).

    Returns: {advanced: int, regressed: int, mean_level: float}.

    Silently no-ops when env has no terrain_importer (cfg portability).
    """
    importer = getattr(env, "terrain_importer", None)
    if importer is None:
        return {"advanced": 0, "regressed": 0, "mean_level": 0.0}

    state = _get_curriculum_state(env)
    advanced_ids: List[int] = []
    regressed_ids: List[int] = []
    for env_idx in env_ids:
        # Per-env distance accumulator (host-managed; we just read it).
        dist = state.get(f"distance_{env_idx}", 0.0)
        if advance_on_success and dist >= distance_threshold:
            advanced_ids.append(env_idx)
            state[f"distance_{env_idx}"] = 0.0  # reset accumulator
        elif regress_on_failure and dist < failure_threshold:
            regressed_ids.append(env_idx)
            state[f"distance_{env_idx}"] = 0.0

    if advanced_ids:
        importer.update_env_origins(
            env_ids=advanced_ids,
            level_deltas=[1] * len(advanced_ids),
        )
    if regressed_ids:
        importer.update_env_origins(
            env_ids=regressed_ids,
            level_deltas=[-1] * len(regressed_ids),
        )

    levels = importer.terrain_levels
    mean_level = sum(levels) / max(1, len(levels))
    return {
        "advanced": len(advanced_ids),
        "regressed": len(regressed_ids),
        "mean_level": mean_level,
    }


def modify_reward_weight(
    env: Any,
    env_ids: List[int],
    term_name: str = "",
    weight: float = 1.0,
    num_steps: int = 10_000,
) -> Dict[str, Any]:
    """Linear ramp of a RewTerm weight over `num_steps` env steps.

    Reads env._steps_v (Vectorised step counter) or env._steps. Updates
    `env.reward_manager.group.terms[term_name].weight` once per call.

    Ramp formula:
      progress = min(1.0, env_step / num_steps)
      effective_weight = progress * weight

    Silently no-ops when env has no reward_manager or term_name missing.
    """
    if not term_name:
        return {"weight": 0.0, "progress": 0.0}

    rm = getattr(env, "reward_manager", None)
    if rm is None or rm.group is None:
        return {"weight": 0.0, "progress": 0.0}
    if term_name not in rm.group.terms:
        return {"weight": 0.0, "progress": 0.0}

    # Pick a step counter (vectorised steps_v[0] preferred; fall back to _steps).
    if hasattr(env, "_steps_v") and env._steps_v:
        step = env._steps_v[0]
    else:
        step = int(getattr(env, "_steps", 0))

    progress = min(1.0, step / max(1, num_steps))
    effective = progress * weight
    rm.group.terms[term_name].weight = effective

    return {"weight": effective, "progress": progress, "target": weight}


def modify_action_scale(
    env: Any,
    env_ids: List[int],
    scale: float = 1.0,
    num_steps: int = 10_000,
    initial_scale: float = 0.1,
) -> Dict[str, Any]:
    """Linear ramp of action scale from `initial_scale` → `scale` over
    `num_steps` env steps. Common pattern for legged locomotion: start
    with small action authority, ramp up as the policy stabilises.

    Mutates `env.cfg.action_scale` (or the iter 30 CartpoleDirectEnv
    equivalent). Silently no-ops when env.cfg has no action_scale.
    """
    cfg = getattr(env, "cfg", None)
    if cfg is None or not hasattr(cfg, "action_scale"):
        return {"scale": 0.0, "progress": 0.0}

    # Step counter.
    if hasattr(env, "_steps_v") and env._steps_v:
        step = env._steps_v[0]
    else:
        step = int(getattr(env, "_steps", 0))

    progress = min(1.0, step / max(1, num_steps))
    effective = initial_scale + progress * (scale - initial_scale)
    cfg.action_scale = effective

    return {"scale": effective, "progress": progress, "target": scale}


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def _get_curriculum_state(env: Any) -> Dict[str, Any]:
    """Lazily initialise + return env._curriculum_state dict.

    Used by terrain_levels_vy to track per-env distance accumulators.
    Host code (the env's step loop) is responsible for actually writing
    `state[f"distance_{env_idx}"]` based on per-step positional change.
    """
    if not hasattr(env, "_curriculum_state"):
        env._curriculum_state = {}
    return env._curriculum_state


def update_distance_accumulator(
    env: Any,
    env_idx: int,
    distance_delta: float,
) -> None:
    """Convenience helper for the host's step loop — add `distance_delta`
    to env._curriculum_state["distance_{env_idx}"]. Initialises if absent.

    Standard usage in DirectRLEnv._physics_step or _post_physics_hook:

        update_distance_accumulator(self, env_idx, abs(x_dot * dt))
    """
    state = _get_curriculum_state(env)
    key = f"distance_{env_idx}"
    state[key] = state.get(key, 0.0) + distance_delta


def reset_distance_accumulator(env: Any, env_idx: int) -> None:
    """Reset the distance accumulator for one env. Called on episode end."""
    state = _get_curriculum_state(env)
    state[f"distance_{env_idx}"] = 0.0
