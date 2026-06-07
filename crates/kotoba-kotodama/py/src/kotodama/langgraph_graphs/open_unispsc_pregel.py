"""UNSPSC hierarchy Pregel graph.

One invocation walks the hierarchy one business boundary at a time:

  segment → family → class → commodity

The caller selects the requested level; the graph executes all ancestors first
so downstream MCP tools receive a complete hierarchy contract.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from kotodama.primitives.open_unispsc import Level, hierarchy_records, record_for_level

try:
    from langgraph.graph import END, StateGraph
    _LANGGRAPH_OK = True
except ImportError:  # pragma: no cover
    END = "END"  # type: ignore[assignment]
    StateGraph = object  # type: ignore[assignment]
    _LANGGRAPH_OK = False


class OpenUnispscState(TypedDict, total=False):
    level: Level
    payload: dict[str, Any]
    target_index: int
    results: Annotated[list[dict[str, Any]], operator.add]
    ok: bool
    error: str


_ORDER: list[Level] = ["segment", "family", "class", "commodity"]


def prepare(state: OpenUnispscState) -> dict[str, Any]:
    level = state.get("level") or "commodity"
    if level not in _ORDER:
        return {"ok": False, "error": f"unsupported level: {level}", "target_index": -1}
    return {"ok": True, "target_index": _ORDER.index(level)}


def _node(level: Level):
    def _run(state: OpenUnispscState) -> dict[str, Any]:
        if state.get("target_index", -1) < _ORDER.index(level):
            return {}
        payload = dict(state.get("payload") or {})
        code = str(payload.get("code") or "")
        payload["code"] = code[: {"segment": 2, "family": 4, "class": 6, "commodity": 8}[level]]
        if level != state.get("level"):
            payload["name"] = ""
        return {"results": [dict(record_for_level(level, payload))]}

    return _run


def finalize(state: OpenUnispscState) -> dict[str, Any]:
    return {"ok": not bool(state.get("error"))}


def build_graph():
    if not _LANGGRAPH_OK:
        return None
    builder = StateGraph(OpenUnispscState)
    builder.add_node("prepare", prepare)
    builder.add_node("segment", _node("segment"))
    builder.add_node("family", _node("family"))
    builder.add_node("class", _node("class"))
    builder.add_node("commodity", _node("commodity"))
    builder.add_node("finalize", finalize)
    builder.set_entry_point("prepare")
    builder.add_edge("prepare", "segment")
    builder.add_edge("segment", "family")
    builder.add_edge("family", "class")
    builder.add_edge("class", "commodity")
    builder.add_edge("commodity", "finalize")
    builder.add_edge("finalize", END)
    return builder.compile()


async def run_open_unispsc(level: Level, payload: dict[str, Any]) -> dict[str, Any]:
    graph = build_graph()
    if graph is None:
        return {"ok": True, "results": [dict(r) for r in hierarchy_records(level, payload)]}
    result = await graph.ainvoke({"level": level, "payload": payload, "results": []})
    return {
        "ok": bool(result.get("ok", True)),
        "level": level,
        "results": result.get("results") or [],
        "error": result.get("error", ""),
    }
