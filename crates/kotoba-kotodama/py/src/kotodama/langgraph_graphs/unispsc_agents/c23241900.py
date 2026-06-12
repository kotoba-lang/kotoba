# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23241900 — Metal boring machines (segment 23).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23241900"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23241900"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Metal boring machines
    spindle_speed_rpm: int
    bore_diameter_mm: float
    coolant_flow_rate: float
    material_hardness_hrc: float


def validate_parameters(state: State) -> dict[str, Any]:
    """Validate boring parameters and set machine defaults."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters"],
        "spindle_speed_rpm": int(inp.get("speed", 1200)),
        "bore_diameter_mm": float(inp.get("diameter", 25.0)),
        "coolant_flow_rate": float(inp.get("coolant", 5.5)),
        "material_hardness_hrc": float(inp.get("hardness", 45.0)),
    }


def calculate_operation_load(state: State) -> dict[str, Any]:
    """Calculate the mechanical load and estimated tool wear."""
    speed = state.get("spindle_speed_rpm", 0)
    hardness = state.get("material_hardness_hrc", 0.0)
    # Heuristic calculation for operation intensity
    load_factor = (speed * hardness) / 500.0
    return {
        "log": [f"{UNISPSC_CODE}:calculate_operation_load"],
        "result": {"estimated_load": load_factor},
    }


def finalize_boring_cycle(state: State) -> dict[str, Any]:
    """Finalize the machine cycle and report status."""
    res = state.get("result") or {}
    load = res.get("estimated_load", 0.0)
    status = "nominal" if load < 1000 else "overload"
    return {
        "log": [f"{UNISPSC_CODE}:finalize_boring_cycle"],
        "result": {
            **res,
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "cycle_status": status,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_parameters)
_g.add_node("calculate", calculate_operation_load)
_g.add_node("finalize", finalize_boring_cycle)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
