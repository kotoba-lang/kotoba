"""
generic.langgraph.run registry — ADR-2604250836 step 2.

Graphs are registered at module import time by the agent module that owns them.
The zeebe_worker_main.py handler looks up by graph_id and calls ainvoke().

Registration pattern (agent module bottom):

    from kotodama.primitives import langgraph_registry
    langgraph_registry.register("my.graph.v1", my_compiled_graph)
"""
from __future__ import annotations

from typing import Any

_REGISTRY: dict[str, Any] = {}


def register(graph_id: str, graph: Any) -> None:
    _REGISTRY[graph_id] = graph


def get(graph_id: str) -> Any | None:
    return _REGISTRY.get(graph_id)


def list_ids() -> list[str]:
    return list(_REGISTRY.keys())
