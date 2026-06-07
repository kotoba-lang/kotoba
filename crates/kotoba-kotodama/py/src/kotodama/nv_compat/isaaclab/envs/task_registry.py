"""task_registry — gym-style task registration for Isaac Lab envs.

Mirror of the registration surface that every Isaac Lab task uses:

    from kotodama.nv_compat.isaaclab.envs.task_registry import register, make
    register(
        id="Isaac-Cartpole-v0",
        entry_point="...:CartpoleDirectEnv",
        env_cfg_entry_point="...:CartpoleDirectEnvCfg",
        max_episode_steps=300,
    )
    env_cfg = parse_env_cfg("Isaac-Cartpole-v0", num_envs=128)
    env = make("Isaac-Cartpole-v0", env_cfg=env_cfg)

Surface:
  - TaskSpec                  — id + entry_point + env_cfg_entry_point +
                                 kwargs + max_episode_steps; per-id record
  - register(id, entry_point, ...) — register a task
  - make(id, **overrides)     — instantiate env (looks up entry_point;
                                 supports passing env_cfg= override)
  - get_task_spec(id)         — return the TaskSpec (or raise)
  - all_task_ids()            — list of registered IDs
  - unregister(id)            — drop a task
  - parse_env_cfg(id, ...)    — instantiate the cfg class + apply overrides
                                 (num_envs, env_spacing, episode_length_s,
                                  any other ctor kwarg). Reads
                                 cfg.attribute_name and accepts both
                                 cfg-class-direct kwargs and nested-dot
                                 paths (e.g. sim.dt → cfg.sim.dt).

Entry points use the `"<module>:<attr>"` convention (matches gymnasium):
the attr is dotted on the imported module to reach a class. The cfg
entry point resolves the same way. Both can be the actual class object
when registration is done programmatically (skipping the import).
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


# ────────────────────────────────────────────────────────────────────────────
# TaskSpec + registry
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class TaskSpec:
    """One registered Isaac Lab task. Mirrors gymnasium.envs.registration.EnvSpec."""
    id: str
    entry_point: Union[str, type]
    env_cfg_entry_point: Union[str, type, None] = None
    kwargs: Dict[str, Any] = field(default_factory=dict)
    max_episode_steps: Optional[int] = None
    # Free-form extras — task-specific metadata (curriculum tags, eval frequency).
    extras: Dict[str, Any] = field(default_factory=dict)

    def resolve_entry_point(self) -> type:
        """Resolve entry_point str/class to a class object."""
        return _resolve(self.entry_point)

    def resolve_env_cfg_entry_point(self) -> Optional[type]:
        """Resolve env_cfg_entry_point — may be None for envs that don't
        carry a separate Cfg class."""
        if self.env_cfg_entry_point is None:
            return None
        return _resolve(self.env_cfg_entry_point)


# Module-level registry.
_REGISTRY: Dict[str, TaskSpec] = {}


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────


def register(
    id: str,
    entry_point: Union[str, type],
    env_cfg_entry_point: Union[str, type, None] = None,
    kwargs: Optional[Dict[str, Any]] = None,
    max_episode_steps: Optional[int] = None,
    extras: Optional[Dict[str, Any]] = None,
    overwrite: bool = False,
) -> TaskSpec:
    """Register a task. Returns the resulting TaskSpec.

    Re-registering an existing id raises ValueError unless `overwrite=True`.
    """
    if not id:
        raise ValueError("task id must be non-empty")
    if id in _REGISTRY and not overwrite:
        raise ValueError(
            f"task '{id}' already registered; pass overwrite=True to replace"
        )
    spec = TaskSpec(
        id=id,
        entry_point=entry_point,
        env_cfg_entry_point=env_cfg_entry_point,
        kwargs=dict(kwargs or {}),
        max_episode_steps=max_episode_steps,
        extras=dict(extras or {}),
    )
    _REGISTRY[id] = spec
    return spec


def unregister(id: str) -> bool:
    """Returns True if the task was registered and removed."""
    return _REGISTRY.pop(id, None) is not None


def get_task_spec(id: str) -> TaskSpec:
    spec = _REGISTRY.get(id)
    if spec is None:
        raise KeyError(
            f"task '{id}' not registered; have: {sorted(_REGISTRY.keys())}"
        )
    return spec


def all_task_ids() -> List[str]:
    """Return sorted list of registered task IDs."""
    return sorted(_REGISTRY.keys())


def num_registered() -> int:
    return len(_REGISTRY)


def clear_registry() -> None:
    """Drop all task registrations. Useful in tests; module init that
    auto-registers tasks must be re-run after."""
    _REGISTRY.clear()


# ────────────────────────────────────────────────────────────────────────────
# parse_env_cfg
# ────────────────────────────────────────────────────────────────────────────


def parse_env_cfg(
    task_name: str,
    num_envs: int = 1,
    use_fabric: bool = True,
    **overrides: Any,
) -> Any:
    """Instantiate the cfg class for a registered task, apply overrides,
    and return the cfg instance.

    Override application is permissive:
      - Top-level kwargs set the matching cfg attribute (skipped silently
        if the cfg has no such attribute; this matches Isaac Lab's
        "extra kwargs are CLI passthrough" convention).
      - Dotted names like `sim.dt=0.005` traverse nested cfg fields
        (cfg.sim.dt = 0.005). Both leaf attribute and intermediate fields
        must exist; missing path → AttributeError.
      - `num_envs` is set after the rest as a convenience for the most
        common CLI override.

    `use_fabric` is forwarded as `cfg.use_fabric` when present (matches
    upstream Isaac Lab GPU-pipeline flag); otherwise silently ignored.
    """
    spec = get_task_spec(task_name)
    cfg_cls = spec.resolve_env_cfg_entry_point()
    if cfg_cls is None:
        raise RuntimeError(
            f"task '{task_name}' has no env_cfg_entry_point — "
            f"register one before calling parse_env_cfg"
        )
    cfg = cfg_cls()

    # Apply overrides (excluding `num_envs` — set last).
    for key, value in overrides.items():
        _set_dotted(cfg, key, value, strict=("." in key))

    # use_fabric (informational — Isaac Lab GPU pipeline flag).
    if hasattr(cfg, "use_fabric"):
        cfg.use_fabric = bool(use_fabric)

    # num_envs last so CLI override always wins.
    if hasattr(cfg, "num_envs"):
        cfg.num_envs = int(num_envs)

    return cfg


def make(task_name: str, env_cfg: Any = None, **make_kwargs: Any) -> Any:
    """Instantiate the env class for a registered task.

    If `env_cfg` is None, calls `parse_env_cfg(task_name, **make_kwargs)`
    to build one; otherwise uses the supplied cfg and `make_kwargs` are
    forwarded as additional ctor kwargs to the env class.

    Returns the env instance.
    """
    spec = get_task_spec(task_name)
    env_cls = spec.resolve_entry_point()
    if env_cfg is None and spec.env_cfg_entry_point is not None:
        env_cfg = parse_env_cfg(task_name, **make_kwargs)
        make_kwargs = {}
    if env_cfg is not None:
        return env_cls(cfg=env_cfg, **make_kwargs)
    return env_cls(**make_kwargs)


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def _resolve(ref: Union[str, type]) -> type:
    """Resolve a string `"module:attr.path"` or class to a class object."""
    if not isinstance(ref, str):
        return ref
    if ":" not in ref:
        raise ValueError(
            f"entry_point string must be 'module:attr' format; got {ref!r}"
        )
    module_path, attr_path = ref.split(":", 1)
    module = importlib.import_module(module_path)
    obj: Any = module
    for part in attr_path.split("."):
        obj = getattr(obj, part)
    return obj


def _set_dotted(target: Any, dotted: str, value: Any,
                 strict: bool = False) -> None:
    """Set `target.<dotted>` = value. When `strict=True`, missing
    intermediate or leaf attributes raise AttributeError; otherwise
    missing top-level attrs are silently ignored (matches Isaac Lab's
    permissive CLI override convention)."""
    parts = dotted.split(".")
    obj = target
    # Walk intermediate parts.
    for part in parts[:-1]:
        if not hasattr(obj, part):
            if strict:
                raise AttributeError(
                    f"cfg has no path '{dotted}': missing intermediate '{part}'"
                )
            return
        obj = getattr(obj, part)
    leaf = parts[-1]
    if not hasattr(obj, leaf):
        if strict:
            raise AttributeError(
                f"cfg has no attribute '{leaf}' (full path '{dotted}')"
            )
        return
    setattr(obj, leaf, value)
