"""
Helper to wrap a single async LangServer-style `task_*` coroutine as a one-node
LangGraph StateGraph. Lets us migrate Zeebe single-step bindings to
LangGraph Server with minimal code (ADR-2605080600 Phase 4).

Usage:
    from kotodama.langgraph_graphs._single_task_wrapper import build_single_task_graph
    from kotodama.kabi_worker_main import task_anastomosis_probe

    graph = build_single_task_graph(task_anastomosis_probe)
    register_graph("kabi.fusionProbe.v1", graph)
"""

from __future__ import annotations

from typing import Any, Callable, TypedDict


class SingleTaskState(TypedDict, total=False):
    input: dict
    output: dict
    ok: bool
    error: str


def build_single_task_graph(task: Callable[..., Any]):
    """Compile a 1-node StateGraph that awaits `task(**state.get('input', {}))`.

    `task` MUST be an async function that returns a JSON-serializable dict.
    Errors are caught and surfaced via state['error'] with ok=False so the
    /runs API can return a clean error envelope rather than crashing.
    """
    async def _node(state: SingleTaskState) -> dict:
        try:
            payload = state.get("input") or {}
            result = await task(**payload) if isinstance(payload, dict) else await task()
            return {"output": result if isinstance(result, dict) else {"value": result}, "ok": True}
        except Exception as exc:
            return {"output": {}, "ok": False, "error": f"{type(exc).__name__}: {exc}"}

    from langgraph.graph import END, StateGraph

    builder = StateGraph(SingleTaskState)
    builder.add_node("invoke", _node)
    builder.set_entry_point("invoke")
    builder.add_edge("invoke", END)
    return builder.compile()


# Named factories for row-driven deployment (P1a). Each one resolves a
# LangServer-style task_* coroutine and wraps it with build_single_task_graph.
# Referenced from vertex_langgraph_assistant.factory_path as
# `kotodama.langgraph_graphs._single_task_wrapper:build_graph_<name>`.

def _factory(task_dotted: str) -> Callable[[], Any]:
    def _build():
        from importlib import import_module
        mod_name, attr = task_dotted.split(":", 1)
        task = getattr(import_module(mod_name), attr)
        return build_single_task_graph(task)
    return _build


build_graph_kobo_budAgent       = _factory("kotodama.kobo_worker_main:task_bud_agent")
build_graph_kobo_sporulate      = _factory("kotodama.kobo_worker_main:task_sporulate")
build_graph_kobo_germinate      = _factory("kotodama.kobo_worker_main:task_germinate")
build_graph_kabi_fusionProbe    = _factory("kotodama.kabi_worker_main:task_anastomosis_probe")
build_graph_kinoko_formBlock    = _factory("kotodama.kinoko_worker_main:task_check_flow_threshold")
build_graph_hakkou_createFerment   = _factory("kotodama.hakkou_worker_main:task_create_ferment_record")
build_graph_hakkou_llmTransform    = _factory("kotodama.hakkou_worker_main:task_llm_transform")
build_graph_hakkou_finalizeFerment = _factory("kotodama.hakkou_worker_main:task_finalize_ferment")
