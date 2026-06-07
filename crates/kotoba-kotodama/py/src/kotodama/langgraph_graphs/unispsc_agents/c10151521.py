# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151521 — Excavator (segment 10).

Bespoke graph logic for heavy machinery operation, focusing on site
preparation, trenching, and material handling workflows.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151521"
UNISPSC_TITLE = "Excavator"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151521"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Excavator
    target_depth_meters: float
    bucket_load_kg: float
    hydraulics_ok: bool
    safety_perimeter_cleared: bool


def inspect(state: State) -> dict[str, Any]:
    """Node: Pre-operation safety and mechanical inspection."""
    inp = state.get("input") or {}
    depth = float(inp.get("depth", 1.5))

    return {
        "log": [f"{UNISPSC_CODE}:inspect"],
        "target_depth_meters": depth,
        "hydraulics_ok": True,
        "safety_perimeter_cleared": True,
    }


def excavate(state: State) -> dict[str, Any]:
    """Node: Simulates the digging process and load calculation."""
    depth = state.get("target_depth_meters", 0.0)
    # Assume 500kg per meter for this simulation
    load = depth * 500.0

    return {
        "log": [f"{UNISPSC_CODE}:excavate (depth: {depth}m)"],
        "bucket_load_kg": load,
    }


def finalize(state: State) -> dict[str, Any]:
    """Node: Records completion and outputs final operational result."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "summary": {
                "excavation_depth": state.get("target_depth_meters"),
                "total_load_kg": state.get("bucket_load_kg"),
                "status": "success",
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect)
_g.add_node("excavate", excavate)
_g.add_node("finalize", finalize)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "excavate")
_g.add_edge("excavate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
