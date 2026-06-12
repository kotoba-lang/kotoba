# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23131600 — Compressor (segment 23).
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23131600"
UNISPSC_TITLE = "Compressor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23131600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Compressor
    pressure_psi: float
    flow_rate_cfm: float
    is_safety_certified: bool
    efficiency_rating: str


def validate_requirements(state: State) -> dict[str, Any]:
    """Inspects the input for compressor technical specifications."""
    inp = state.get("input") or {}
    psi = inp.get("psi", 0.0)
    cfm = inp.get("cfm", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "pressure_psi": float(psi),
        "flow_rate_cfm": float(cfm),
        "is_safety_certified": inp.get("certified", False)
    }


def analyze_performance(state: State) -> dict[str, Any]:
    """Calculates efficiency based on pressure and flow rate."""
    psi = state.get("pressure_psi", 0.0)
    cfm = state.get("flow_rate_cfm", 0.0)

    if psi > 150 and cfm > 20:
        rating = "Industrial High"
    elif psi > 90:
        rating = "Standard Commercial"
    else:
        rating = "Residential/Light"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_performance"],
        "efficiency_rating": rating
    }


def finalize_asset_data(state: State) -> dict[str, Any]:
    """Wraps the analysis into the final result manifest."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_data"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "psi": state.get("pressure_psi"),
                "cfm": state.get("flow_rate_cfm"),
                "rating": state.get("efficiency_rating")
            },
            "certified": state.get("is_safety_certified", False),
            "status": "active"
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requirements)
_g.add_node("analyze", analyze_performance)
_g.add_node("finalize", finalize_asset_data)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
