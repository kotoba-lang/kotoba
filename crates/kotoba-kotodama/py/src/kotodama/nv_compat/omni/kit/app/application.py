"""Application — Kit app singleton + extension lifecycle.

Mirrors `omni.kit.app.IApp` / `omni.kit.app.get_app()` (Omniverse Kit 105+).
The Application owns an ordered set of registered IExt instances and
dispatches startup / shutdown in dependency-respecting order.

Dependency resolution: each extension declares dependencies via its
ExtensionToml. The Application sorts extensions by topological order so
parents start before children and shutdown is reverse order. Cyclic
dependencies raise RuntimeError.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .extension import ExtensionToml, IExt


@dataclass
class _RegisteredExt:
    ext_id: str
    instance: IExt
    toml: Optional[ExtensionToml] = None
    started: bool = False


@dataclass
class Application:
    """Singleton app shell. Use `get_app()` to access the global instance."""
    _extensions: Dict[str, _RegisteredExt] = field(default_factory=dict)
    _startup_log: List[str] = field(default_factory=list)
    _shutdown_log: List[str] = field(default_factory=list)

    def register_extension(self, ext_id: str, instance: IExt,
                           toml: Optional[ExtensionToml] = None) -> None:
        """Register an IExt instance under `ext_id`. Idempotent on re-register."""
        self._extensions[ext_id] = _RegisteredExt(
            ext_id=ext_id, instance=instance, toml=toml,
        )

    def unregister_extension(self, ext_id: str) -> None:
        """Unregister an extension (shuts it down first if started)."""
        if ext_id not in self._extensions:
            return
        ext = self._extensions[ext_id]
        if ext.started:
            ext.instance.on_shutdown()
            ext.started = False
        del self._extensions[ext_id]

    def get_extension(self, ext_id: str) -> Optional[IExt]:
        ext = self._extensions.get(ext_id)
        return ext.instance if ext else None

    def get_extension_ids(self) -> List[str]:
        return list(self._extensions.keys())

    def _topological_order(self) -> List[str]:
        """Kahn's algorithm over extensions ordered by their dependencies."""
        # Build adjacency: ext_id → list of dep_ids (depends-on relation)
        deps_map: Dict[str, List[str]] = {}
        for ext_id, ext in self._extensions.items():
            deps_map[ext_id] = []
            if ext.toml is not None:
                for dep_id in ext.toml.dependencies.keys():
                    if dep_id in self._extensions:  # only registered deps matter
                        deps_map[ext_id].append(dep_id)
        # Compute in-degree (number of unsatisfied dependencies per ext).
        in_degree = {eid: len(deps) for eid, deps in deps_map.items()}
        # Start with extensions with no deps.
        ready: List[str] = sorted([eid for eid, d in in_degree.items() if d == 0])
        order: List[str] = []
        while ready:
            eid = ready.pop(0)
            order.append(eid)
            # Find extensions that depend on this one and decrement their in-degree.
            for other_eid, other_deps in deps_map.items():
                if eid in other_deps:
                    in_degree[other_eid] -= 1
                    if in_degree[other_eid] == 0:
                        ready.append(other_eid)
            ready.sort()
        if len(order) != len(self._extensions):
            raise RuntimeError("Cyclic dependency in extensions; cannot order startup")
        return order

    def startup_all(self) -> List[str]:
        """Fire on_startup for all registered extensions in dependency order.
        Returns the order in which extensions were started.
        """
        order = self._topological_order()
        self._startup_log = []
        for eid in order:
            ext = self._extensions[eid]
            if not ext.started:
                ext.instance.on_startup(eid)
                ext.started = True
                self._startup_log.append(eid)
        return list(self._startup_log)

    def shutdown_all(self) -> List[str]:
        """Fire on_shutdown for all started extensions in REVERSE order.
        Falls back to registration order if topological resolution fails
        (e.g. cyclic dependency after startup_all errored)."""
        try:
            order = self._topological_order()
        except RuntimeError:
            order = list(self._extensions.keys())
        self._shutdown_log = []
        for eid in reversed(order):
            ext = self._extensions[eid]
            if ext.started:
                ext.instance.on_shutdown()
                ext.started = False
                self._shutdown_log.append(eid)
        return list(self._shutdown_log)

    def num_extensions(self) -> int:
        return len(self._extensions)

    def num_started(self) -> int:
        return sum(1 for ext in self._extensions.values() if ext.started)


# ── Global singleton accessor ─────────────────────────────────────────────

_GLOBAL_APP: Optional[Application] = None


def get_app() -> Application:
    """Return the global Application singleton, creating it on first call.
    Mirrors `omni.kit.app.get_app()`.
    """
    global _GLOBAL_APP
    if _GLOBAL_APP is None:
        _GLOBAL_APP = Application()
    return _GLOBAL_APP


def reset_app() -> None:
    """Drop the global singleton. For testing / re-init."""
    global _GLOBAL_APP
    if _GLOBAL_APP is not None:
        _GLOBAL_APP.shutdown_all()
    _GLOBAL_APP = None
