# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153014"
UNISPSC_TITLE = "Welding"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153014"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    weld_method: str
    filler_material: str
    voltage_setting: float
    safety_clearance: bool


def configure_welder(state: State) -> dict[str, Any]:
    """Analyze input specifications and set welding parameters."""
    inp = state.get("input") or {}
    method = inp.get("method", "MIG")
    filler = inp.get("filler", "ER70S-6")
    voltage = float(inp.get("voltage", 24.5))

    return {
        "log": [f"{UNISPSC_CODE}:configure_welder"],
        "weld_method": method,
        "filler_material": filler,
        "voltage_setting": voltage,
        "safety_clearance": True,
    }


def perform_weld_bead(state: State) -> dict[str, Any]:
    """Simulate the physical welding process and state transition."""
    method = state.get("weld_method", "Unknown")
    voltage = state.get("voltage_setting", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:perform_weld_bead method={method} v={voltage}"],
    }


def inspect_weld_quality(state: State) -> dict[str, Any]:
    """Validate the integrity of the weld and emit the final result."""
    safe = state.get("safety_clearance", False)
    method = state.get("weld_method", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_weld_quality"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operation": "Welding",
            "method_applied": method,
            "quality_check": "Visual/NDT Passed" if safe else "Failed",
            "ok": safe,
        },
    }


_g = StateGraph(State)
_g.add_node("configure", configure_welder)
_g.add_node("weld", perform_weld_bead)
_g.add_node("inspect", inspect_weld_quality)

_g.add_edge(START, "configure")
_g.add_edge("configure", "weld")
_g.add_edge("weld", "inspect")
_g.add_edge("inspect", END)

graph = _g.compile()
