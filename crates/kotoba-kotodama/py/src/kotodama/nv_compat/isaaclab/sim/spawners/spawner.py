"""SpawnerCfgBase + SpawnedPrim record + module-level registry.

Lightweight registry pattern: every spawn_* call appends a `SpawnedPrim`
to the active `SpawnedPrimRegistry`. A renderer subscriber reads via
`get_registry().prims()` to instantiate real Stage prims.

Multiple registries can coexist via the push/pop stack (test isolation,
nested scenes). `get_registry()` returns the top of the stack.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ────────────────────────────────────────────────────────────────────────────
# Cfg base + prim record
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class SpawnerCfgBase:
    """Common base for every spawner cfg. Mirrors Isaac Lab's pattern:

      - color:     RGB tuple in [0, 1] (matches UsdGeom DisplayColor)
      - mass:      kg (optional; defaults to 0 = static)
      - collision_enabled: whether physics treats the prim as a collider
      - visible:   visibility toggle
      - extras:    free-form per-prim payload (label, semantics class, etc.)
    """
    color: tuple = (1.0, 1.0, 1.0)
    mass: float = 0.0
    collision_enabled: bool = True
    visible: bool = True
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpawnedPrim:
    """One spawn request record kept by the registry."""
    path: str
    kind: str                                 # "cuboid" / "sphere" / "light" / "usd_file" / ...
    cfg: Any                                  # the typed cfg dataclass
    translation: tuple = (0.0, 0.0, 0.0)
    orientation: tuple = (0.0, 0.0, 0.0, 1.0) # (x, y, z, w)
    scale: tuple = (1.0, 1.0, 1.0)
    extras: Dict[str, Any] = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────────────
# Registry
# ────────────────────────────────────────────────────────────────────────────


class SpawnedPrimRegistry:
    """Append-only registry of SpawnedPrim records.

    Methods:
      - add(prim) → idempotent on path (replaces prior entry)
      - prims()   → list snapshot
      - by_path(p) / by_kind(k)
      - clear()
      - num_prims()
    """

    def __init__(self):
        self._prims: Dict[str, SpawnedPrim] = {}

    def add(self, prim: SpawnedPrim) -> None:
        """Add or replace a prim record by path (paths are unique)."""
        self._prims[prim.path] = prim

    def prims(self) -> List[SpawnedPrim]:
        """Snapshot of registered prims in insertion order."""
        return list(self._prims.values())

    def by_path(self, path: str) -> Optional[SpawnedPrim]:
        return self._prims.get(path)

    def by_kind(self, kind: str) -> List[SpawnedPrim]:
        return [p for p in self._prims.values() if p.kind == kind]

    def clear(self) -> None:
        self._prims.clear()

    def num_prims(self) -> int:
        return len(self._prims)

    def __len__(self) -> int:
        return len(self._prims)

    def __contains__(self, path: str) -> bool:
        return path in self._prims


# Module-level registry stack. The bottom is a default registry; push/pop
# allows nested scenes (tests, multi-scene apps).
_REGISTRY_STACK: List[SpawnedPrimRegistry] = [SpawnedPrimRegistry()]


def get_registry() -> SpawnedPrimRegistry:
    """Returns the active registry (top of the stack)."""
    return _REGISTRY_STACK[-1]


def push_registry(registry: Optional[SpawnedPrimRegistry] = None) -> SpawnedPrimRegistry:
    """Push a new (or supplied) registry as the active one. Returns it.

    Mirror of Isaac Lab's per-Stage active-registry pattern. Use in tests
    to isolate spawn requests:

        push_registry()
        try:
            spawn_cuboid(...)
            assert get_registry().num_prims() == 1
        finally:
            pop_registry()
    """
    reg = registry if registry is not None else SpawnedPrimRegistry()
    _REGISTRY_STACK.append(reg)
    return reg


def pop_registry() -> SpawnedPrimRegistry:
    """Pop the top registry. Returns the popped instance. The bottom
    registry is never popped (always retains at least one)."""
    if len(_REGISTRY_STACK) == 1:
        raise RuntimeError("cannot pop the bottom registry")
    return _REGISTRY_STACK.pop()
