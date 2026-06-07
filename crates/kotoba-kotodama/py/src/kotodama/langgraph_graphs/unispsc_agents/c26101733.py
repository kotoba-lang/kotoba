# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101733 — Carburetor jet (segment 26).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101733"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101733"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    orifice_diameter_mm: float
    flow_rate_cc_min: float
    thread_specification: str
    fuel_compatibility: str
    inspection_verified: bool


def validate_mechanicals(state: State) -> dict[str, Any]:
    """Validates the physical dimensions and specifications of the carburetor jet."""
    inp = state.get("input") or {}
    diameter = float(inp.get("diameter", 0.0))
    thread = str(inp.get("thread", "M5x0.8"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_mechanicals"],
        "orifice_diameter_mm": diameter,
        "thread_specification": thread,
    }


def analyze_flow_rate(state: State) -> dict[str, Any]:
    """Calculates the theoretical flow rate based on the measured orifice size."""
    diameter = state.get("orifice_diameter_mm", 0.0)
    # Simple calculation: Area (proportional to diameter squared) * factor
    theoretical_flow = (diameter ** 2) * 450.0

    return {
        "log": [f"{UNISPSC_CODE}:analyze_flow_rate"],
        "flow_rate_cc_min": theoretical_flow,
        "fuel_compatibility": "Gasoline/Ethanol" if diameter > 0.0 else "None",
    }


def certify_component(state: State) -> dict[str, Any]:
    """Finalizes the component data and performs certification check."""
    diameter = state.get("orifice_diameter_mm", 0.0)
    flow = state.get("flow_rate_cc_min", 0.0)

    verified = diameter > 0.0 and flow > 0.0

    return {
        "log": [f"{UNISPSC_CODE}:certify_component"],
        "inspection_verified": verified,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "CERTIFIED" if verified else "FAILED_INSPECTION",
            "metrics": {
                "orifice": diameter,
                "flow": flow,
                "thread": state.get("thread_specification"),
                "compatibility": state.get("fuel_compatibility"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_mechanicals)
_g.add_node("analyze", analyze_flow_rate)
_g.add_node("certify", certify_component)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
