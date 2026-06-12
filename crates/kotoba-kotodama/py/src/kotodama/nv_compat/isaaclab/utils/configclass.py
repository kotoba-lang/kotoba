"""isaaclab.utils.configclass — cfg dataclass decorator.

Mirror of `isaaclab.utils.configclass.configclass` (Isaac Lab 1.x). The
canonical Isaac Lab cfg decorator — wraps a plain class as a dataclass
with four useful additions:

  1. **Mutable-default auto-wrap**: bare `list` / `dict` / `set` defaults
     are auto-wrapped in `field(default_factory=...)` so each instance gets
     its own copy (avoiding the classic shared-default Python gotcha).
  2. **to_dict() / from_dict() shortcuts**: thin wrappers over iter 47's
     utils.dict.class_to_dict / update_class_from_dict.
  3. **replace(**kwargs)**: immutable-style update that returns a new
     instance with the supplied fields overridden (matches dataclasses.replace).
  4. **copy()**: deep clone via to_dict round-trip (preserves nested cfg
     classes correctly when they are themselves configclass-decorated).

Standard usage:

    @configclass
    class MyEnvCfg:
        num_envs: int = 1
        physics_dt: float = 1/60
        joint_names: list = ["hip", "knee"]   # auto-wrapped to default_factory
        sim: "SimCfg" = SimCfg()              # nested cfg

    cfg = MyEnvCfg()
    cfg.num_envs = 16
    d = cfg.to_dict()
    cfg2 = MyEnvCfg.from_dict(d)
    cfg3 = cfg.replace(num_envs=32)
    cfg4 = cfg.copy()

Implementation: applies `@dataclass(eq=False)` after rewriting class
annotations (auto-wrap mutable defaults) and injecting the four
convenience methods. `eq=False` matches Isaac Lab (cfg equality by
identity, not by field — avoids surprise inequality from float-near-equal
fields). Inherited bases that are themselves configclasses are honored.

Pure stdlib (dataclasses + copy).
"""

from __future__ import annotations

import copy as _copy
from dataclasses import (
    MISSING,
    dataclass,
    field,
    fields,
    is_dataclass,
)
from typing import Any, Dict, Type, TypeVar

from .dict import class_to_dict, update_class_from_dict


T = TypeVar("T")


# ────────────────────────────────────────────────────────────────────────────
# Mutable-default auto-wrap helpers
# ────────────────────────────────────────────────────────────────────────────


def _is_mutable_default(value: Any) -> bool:
    """True if a class-attribute default needs default_factory wrapping.

    Mutable types covered:
      - list / dict / set / bytearray  (Python's flagged mutables)
      - **any class instance with __dict__** (e.g. another configclass —
        shared default would cause cross-instance contamination)

    Immutable defaults that pass through unchanged:
      - None
      - bool / int / float / str / bytes / complex
      - frozenset
      - tuple  (treated as immutable; if it contains mutables that's the
        caller's problem, matching Isaac Lab convention)
      - types / functions / methods / classes themselves
    """
    if isinstance(value, (list, dict, set, bytearray)):
        return True
    # Class instances with __dict__ are shared by default — wrap them.
    if hasattr(value, "__dict__") and not isinstance(value, type):
        # Exclude built-in callables (function, method) which lack __dict__
        # of significance for cfg state.
        if callable(value) and not is_dataclass(value):
            return False
        return True
    return False


def _wrap_mutable_defaults(cls: Type[T]) -> None:
    """Rewrite class-attribute defaults: any mutable default is replaced
    with `field(default_factory=lambda: copy.deepcopy(value))` so each
    instance gets its own copy.

    This pre-processes the class in-place BEFORE @dataclass is applied
    so dataclasses.dataclass sees a default_factory it accepts.

    Python 3.14 lazy-evaluates `__annotations__` (PEP 649) — accessing
    via `cls.__dict__.get("__annotations__")` returns empty before the
    descriptor fires; using `inspect.get_annotations(cls)` forces
    evaluation and works across all Python versions.
    """
    import inspect
    annotations = inspect.get_annotations(cls)
    for name in list(annotations.keys()):
        if name not in cls.__dict__:
            continue
        default = cls.__dict__[name]
        if _is_mutable_default(default):
            # Capture-by-value via default arg (avoids late-binding closure bug).
            snapshot = _copy.deepcopy(default)
            setattr(cls, name, field(default_factory=lambda v=snapshot: _copy.deepcopy(v)))


# ────────────────────────────────────────────────────────────────────────────
# to_dict / from_dict / replace / copy injections
# ────────────────────────────────────────────────────────────────────────────


def _inject_helpers(cls: Type[T]) -> None:
    """Add to_dict / from_dict / replace / copy methods to `cls`."""

    def to_dict(self) -> Dict[str, Any]:
        """Recursively serialize this cfg + nested cfgs to a plain dict."""
        return class_to_dict(self)

    @classmethod
    def from_dict(cls_, d: Dict[str, Any]) -> Any:
        """Build a fresh instance + apply `d` via update_class_from_dict.

        Unknown keys in `d` are silently ignored (matches Isaac Lab
        permissive checkpoint-restore semantics)."""
        instance = cls_()
        update_class_from_dict(instance, d, strict=False)
        return instance

    def replace(self, **kwargs: Any) -> Any:
        """Return a new instance with the supplied fields overridden.

        Mirrors dataclasses.replace but routes through copy() first so
        nested mutables aren't shared with the original.
        """
        new = self.copy()
        for key, value in kwargs.items():
            if not hasattr(new, key):
                raise AttributeError(
                    f"{type(self).__name__} has no field '{key}'"
                )
            setattr(new, key, value)
        return new

    def copy(self) -> Any:
        """Deep-clone this cfg. Nested cfgs (including nested configclass
        instances) are copied recursively."""
        return _copy.deepcopy(self)

    cls.to_dict = to_dict  # type: ignore[attr-defined]
    cls.from_dict = from_dict  # type: ignore[attr-defined]
    cls.replace = replace  # type: ignore[attr-defined]
    cls.copy = copy  # type: ignore[attr-defined]


# ────────────────────────────────────────────────────────────────────────────
# @configclass decorator
# ────────────────────────────────────────────────────────────────────────────


def configclass(cls: Type[T] = None, /, **dataclass_kwargs: Any) -> Type[T]:
    """Decorator: convert a class into an Isaac Lab cfg dataclass.

    Standard usage (no parens):

        @configclass
        class MyCfg:
            ...

    With dataclass kwargs:

        @configclass(frozen=True)
        class MyImmutableCfg:
            ...

    Default dataclass kwargs:
      - eq=False        (Isaac Lab convention — equality by identity)
      - repr=True       (default)
      - init=True       (default)
      - frozen=False    (default)

    The decorator order is: mutable-default wrap → @dataclass → inject
    to_dict/from_dict/replace/copy methods.
    """

    def wrap(c: Type[T]) -> Type[T]:
        # 1. Wrap mutable defaults.
        _wrap_mutable_defaults(c)
        # 2. Apply @dataclass with Isaac Lab defaults.
        kwargs = {"eq": False}
        kwargs.update(dataclass_kwargs)
        c = dataclass(**kwargs)(c)
        # 3. Inject helpers.
        _inject_helpers(c)
        return c

    # Decorator with or without args.
    if cls is not None:
        # @configclass (no parens) — cls is the class.
        return wrap(cls)
    # @configclass(...) — return the wrapper.
    return wrap  # type: ignore[return-value]


# ────────────────────────────────────────────────────────────────────────────
# Helper: is_configclass introspection
# ────────────────────────────────────────────────────────────────────────────


def is_configclass(obj: Any) -> bool:
    """True if `obj` is a configclass-decorated class or instance.

    Detected by the presence of all four injected methods. A plain
    @dataclass without @configclass returns False.
    """
    return (
        is_dataclass(obj)
        and hasattr(obj, "to_dict")
        and hasattr(obj, "from_dict")
        and hasattr(obj, "replace")
        and hasattr(obj, "copy")
    )
