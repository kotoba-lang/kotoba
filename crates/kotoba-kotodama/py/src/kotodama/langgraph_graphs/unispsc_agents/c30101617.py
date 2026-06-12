# codemod:2605231300-unispsc-placeholder v1
"""
Unispsc actor agent c30101617 — Spec (segment 30).

Placeholder graph emitted by the 2026-05-23 corpus rebuild codemod. The
upstream Gemini exec rebuild will overwrite this file with bespoke per-
code logic; until then this 3-node compliance/process/emit pipeline
ensures the agent is callable from UnispscAgentExecutorCell and exercises
the MstCheckpointSaver substrate path.

This module is regenerated automatically — hand-edit at your own risk.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "30101617"
UNISPSC_TITLE = "Spec"
UNISPSC_SEGMENT = "30"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c30101617"


class State(TypedDict, total=False):
    input: dict[str, Any]
    compliance_check: bool
    log: Annotated[list[str], add]
    result: dict[str, Any]


def receive(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:receive"],
        "compliance_check": bool(inp),
    }


def process(state: State) -> dict[str, Any]:
    return {"log": [f"{UNISPSC_CODE}:process"]}


def emit(state: State) -> dict[str, Any]:
    return {
        "log": [f"{UNISPSC_CODE}:emit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("receive", receive)
_g.add_node("process", process)
_g.add_node("emit", emit)
_g.add_edge(START, "receive")
_g.add_edge("receive", "process")
_g.add_edge("process", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
