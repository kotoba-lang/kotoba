"""isaaclab.envs.common — VecEnv types + spaces helpers.

Mirror of `isaaclab.envs.common` (Isaac Lab 1.x). Foundational type
definitions + space helpers shared across the three env families
(ManagerBasedRLEnv / DirectRLEnv / DirectMARLEnv).

Surface:
  - VecEnvObs              — TypedDict: per-group observation buffers
  - VecEnvStepReturn       — 5-tuple type: (obs, reward, terminated,
                              truncated, info) matching the canonical
                              env.step() return shape
  - VecEnvResetReturn      — 2-tuple type: (obs, info)
  - ObsBuf / RewardBuf / DoneBuf — type aliases for list-of-per-env vectors
  - SpaceCfg dataclasses   — `gymnasium.spaces.Box` / `Discrete` /
                              `MultiDiscrete` / `MultiBinary` / `Dict` /
                              `Tuple` analogs that serialize cleanly
                              (Isaac Lab pattern: spaces declared in cfg
                              rather than instantiated)
  - spec_to_dict / dict_to_spec
                            — round-trip a SpaceCfg ↔ dict for YAML
                              checkpoint compatibility
  - flatten_obs(obs_dict)  — concat all groups into one flat list
                              (matches stable-baselines3 / RL libs that
                              expect a single observation tensor)
  - infer_action_dim(env)  — pull action_dim from env / env.cfg
  - infer_observation_shape(obs) — inspect obs to derive shape tuple

Pure stdlib. No gym / gymnasium dependency — these are cfg dataclasses
that mirror the gym space surface for declarative env description.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union


# ────────────────────────────────────────────────────────────────────────────
# Type aliases + TypedDicts
# ────────────────────────────────────────────────────────────────────────────


# Per-group observation: {group_name: per-env-flat-floats}.
VecEnvObs = Dict[str, List[float]]

# Per-env scalar / bool buffers.
ObsBuf = List[List[float]]
RewardBuf = List[float]
DoneBuf = List[bool]
InfoBuf = Dict[str, Any]

# Canonical step return: matches gym/gymnasium 5-tuple convention.
VecEnvStepReturn = Tuple[VecEnvObs, RewardBuf, DoneBuf, DoneBuf, InfoBuf]
# Canonical reset return.
VecEnvResetReturn = Tuple[VecEnvObs, InfoBuf]


# ────────────────────────────────────────────────────────────────────────────
# SpaceCfg dataclasses — declarative gym.spaces analogs
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class SpaceCfgBase:
    """Common base. `kind` discriminates Box/Discrete/etc."""
    kind: str = "base"


@dataclass
class BoxSpaceCfg(SpaceCfgBase):
    """Continuous-valued vector space. Mirror of gymnasium.spaces.Box."""
    low: Union[float, List[float]] = -math.inf
    high: Union[float, List[float]] = math.inf
    shape: Tuple[int, ...] = (1,)
    dtype: str = "float32"
    kind: str = "box"


@dataclass
class DiscreteSpaceCfg(SpaceCfgBase):
    """Single integer in [0, n). Mirror of gymnasium.spaces.Discrete."""
    n: int = 2
    start: int = 0
    kind: str = "discrete"


@dataclass
class MultiDiscreteSpaceCfg(SpaceCfgBase):
    """Vector of independent discrete spaces. Mirror of
    gymnasium.spaces.MultiDiscrete."""
    nvec: List[int] = field(default_factory=list)
    kind: str = "multi_discrete"


@dataclass
class MultiBinarySpaceCfg(SpaceCfgBase):
    """N independent 0/1 dims. Mirror of gymnasium.spaces.MultiBinary."""
    n: int = 1
    kind: str = "multi_binary"


@dataclass
class DictSpaceCfg(SpaceCfgBase):
    """Nested dict of sub-spaces. Mirror of gymnasium.spaces.Dict."""
    spaces: Dict[str, Any] = field(default_factory=dict)
    kind: str = "dict"


@dataclass
class TupleSpaceCfg(SpaceCfgBase):
    """Ordered tuple of sub-spaces. Mirror of gymnasium.spaces.Tuple."""
    spaces: List[Any] = field(default_factory=list)
    kind: str = "tuple"


# ────────────────────────────────────────────────────────────────────────────
# spec_to_dict / dict_to_spec
# ────────────────────────────────────────────────────────────────────────────


_SPEC_KIND_TO_CLS = {
    "box": BoxSpaceCfg,
    "discrete": DiscreteSpaceCfg,
    "multi_discrete": MultiDiscreteSpaceCfg,
    "multi_binary": MultiBinarySpaceCfg,
    "dict": DictSpaceCfg,
    "tuple": TupleSpaceCfg,
}


def spec_to_dict(spec: SpaceCfgBase) -> Dict[str, Any]:
    """Round-trip a SpaceCfg to a YAML-safe dict.

    Nested Dict / Tuple spaces recurse through their members.
    """
    if not isinstance(spec, SpaceCfgBase):
        raise TypeError(
            f"spec_to_dict expects SpaceCfgBase; got {type(spec).__name__}"
        )
    if isinstance(spec, DictSpaceCfg):
        return {
            "kind": "dict",
            "spaces": {k: spec_to_dict(v) for k, v in spec.spaces.items()},
        }
    if isinstance(spec, TupleSpaceCfg):
        return {
            "kind": "tuple",
            "spaces": [spec_to_dict(s) for s in spec.spaces],
        }
    if isinstance(spec, BoxSpaceCfg):
        return {
            "kind": "box",
            "low": spec.low, "high": spec.high,
            "shape": list(spec.shape), "dtype": spec.dtype,
        }
    if isinstance(spec, DiscreteSpaceCfg):
        return {"kind": "discrete", "n": spec.n, "start": spec.start}
    if isinstance(spec, MultiDiscreteSpaceCfg):
        return {"kind": "multi_discrete", "nvec": list(spec.nvec)}
    if isinstance(spec, MultiBinarySpaceCfg):
        return {"kind": "multi_binary", "n": spec.n}
    return {"kind": spec.kind}


def dict_to_spec(d: Dict[str, Any]) -> SpaceCfgBase:
    """Reverse of spec_to_dict — build a SpaceCfg from a plain dict.

    Raises ValueError on unknown `kind`.
    """
    if not isinstance(d, dict) or "kind" not in d:
        raise ValueError(f"dict_to_spec requires dict with 'kind' field; got {d!r}")
    kind = d["kind"]
    cls = _SPEC_KIND_TO_CLS.get(kind)
    if cls is None:
        raise ValueError(
            f"unknown space kind {kind!r}; supported: {sorted(_SPEC_KIND_TO_CLS.keys())}"
        )
    if kind == "dict":
        return DictSpaceCfg(
            spaces={k: dict_to_spec(v) for k, v in d.get("spaces", {}).items()},
        )
    if kind == "tuple":
        return TupleSpaceCfg(
            spaces=[dict_to_spec(s) for s in d.get("spaces", [])],
        )
    if kind == "box":
        return BoxSpaceCfg(
            low=d.get("low", -math.inf),
            high=d.get("high", math.inf),
            shape=tuple(d.get("shape", (1,))),
            dtype=d.get("dtype", "float32"),
        )
    if kind == "discrete":
        return DiscreteSpaceCfg(n=int(d["n"]), start=int(d.get("start", 0)))
    if kind == "multi_discrete":
        return MultiDiscreteSpaceCfg(nvec=list(d.get("nvec", [])))
    if kind == "multi_binary":
        return MultiBinarySpaceCfg(n=int(d.get("n", 1)))
    return SpaceCfgBase(kind=kind)


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def flatten_obs(obs_dict: VecEnvObs) -> List[float]:
    """Concat every group's observation list into one flat list. Group
    iteration follows insertion order (Python dict guarantee since 3.7).

    Standard usage with stable-baselines3 / rl_games which expect a single
    obs tensor:

        obs_dict = env.step_managed(action)["observations"]
        flat = flatten_obs(obs_dict)        # → single list of floats
    """
    if not isinstance(obs_dict, dict):
        raise TypeError(
            f"flatten_obs expects dict; got {type(obs_dict).__name__}"
        )
    out: List[float] = []
    for group_name, group_obs in obs_dict.items():
        if isinstance(group_obs, list):
            out.extend(group_obs)
        elif group_obs is None:
            continue
        else:
            raise TypeError(
                f"obs group '{group_name}' must be list; got "
                f"{type(group_obs).__name__}"
            )
    return out


def infer_action_dim(env: Any) -> int:
    """Pull action_dim from env / env.cfg with several fallbacks.

    Lookup order:
      1. env.action_space["shape"][0]
      2. env.cfg.num_actions
      3. env.action_dim
      4. env.num_actions

    Raises AttributeError if none of those resolve to an int.
    """
    # action_space dict pattern (DirectRLEnv style).
    space = getattr(env, "action_space", None)
    if isinstance(space, dict) and "shape" in space:
        shape = space["shape"]
        if isinstance(shape, (tuple, list)) and shape:
            return int(shape[0])
    # cfg.num_actions.
    cfg = getattr(env, "cfg", None)
    if cfg is not None:
        for attr in ("num_actions", "action_dim"):
            v = getattr(cfg, attr, None)
            if isinstance(v, int):
                return v
    # Direct attrs.
    for attr in ("action_dim", "num_actions"):
        v = getattr(env, attr, None)
        if isinstance(v, int):
            return v
    raise AttributeError(
        f"could not infer action_dim from env {type(env).__name__}; "
        f"expected env.action_space[shape] / env.cfg.num_actions / "
        f"env.action_dim / env.num_actions"
    )


def infer_observation_shape(obs: Union[VecEnvObs, List[float], List[List[float]]]) -> Tuple[int, ...]:
    """Inspect an observation buffer to derive its shape.

    Handles three forms:
      - dict (VecEnvObs): returns (num_groups, max_group_len) — collapses
        ragged groups to the max length (caller may want to flatten first)
      - flat list[float]: returns (len,)
      - list[list[float]]: returns (num_envs, group_len)

    Raises TypeError on other shapes.
    """
    if isinstance(obs, dict):
        if not obs:
            return (0,)
        lengths = [len(v) for v in obs.values() if isinstance(v, list)]
        if not lengths:
            return (0,)
        return (len(obs), max(lengths))
    if isinstance(obs, list):
        if not obs:
            return (0,)
        if isinstance(obs[0], (int, float)):
            return (len(obs),)
        if isinstance(obs[0], list):
            return (len(obs), max(len(row) for row in obs))
    raise TypeError(
        f"infer_observation_shape expects dict | list; got {type(obs).__name__}"
    )


def space_shape(space: SpaceCfgBase) -> Tuple[int, ...]:
    """Return the per-instance shape of a SpaceCfg.

      - BoxSpaceCfg → cfg.shape
      - DiscreteSpaceCfg → (1,)
      - MultiDiscreteSpaceCfg → (len(nvec),)
      - MultiBinarySpaceCfg → (n,)
      - DictSpaceCfg → (sum of sub-space shapes[0] if all 1D, else raises)
      - TupleSpaceCfg → analogous
    """
    if isinstance(space, BoxSpaceCfg):
        return tuple(space.shape)
    if isinstance(space, DiscreteSpaceCfg):
        return (1,)
    if isinstance(space, MultiDiscreteSpaceCfg):
        return (len(space.nvec),)
    if isinstance(space, MultiBinarySpaceCfg):
        return (space.n,)
    if isinstance(space, DictSpaceCfg):
        total = 0
        for s in space.spaces.values():
            sub = space_shape(s)
            if len(sub) != 1:
                raise ValueError(
                    f"Dict space contains a non-1D sub-space {sub}; "
                    f"flatten manually"
                )
            total += sub[0]
        return (total,)
    if isinstance(space, TupleSpaceCfg):
        total = 0
        for s in space.spaces:
            sub = space_shape(s)
            if len(sub) != 1:
                raise ValueError(
                    f"Tuple space contains a non-1D sub-space {sub}"
                )
            total += sub[0]
        return (total,)
    raise TypeError(f"unsupported space type: {type(space).__name__}")
