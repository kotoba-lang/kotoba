"""Builtin echo graph — moved from inline _register_echo_graph() to a module
so it can be referenced by a vertex_langgraph_assistant row (kind=py_factory)."""

from __future__ import annotations

from typing import TypedDict


class EchoState(TypedDict, total=False):
    input: str
    output: str


def _echo_node(state: EchoState) -> dict:
    return {"output": f"echo: {state.get('input', '')}"}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(EchoState)
    builder.add_node("echo", _echo_node)
    builder.set_entry_point("echo")
    builder.add_edge("echo", END)
    return builder.compile()
