# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23121501 — Compressor.
Bespoke LangGraph logic for industrial compression systems.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23121501"
UNISPSC_TITLE = "Compressor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23121501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Compressor
    pressure_psi: float
    flow_cfm: float
    efficiency_rating: float
    maintenance_status: str


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the operational specifications for the compressor unit."""
    inp = state.get("input") or {}
    psi = float(inp.get("pressure_psi", 100.0))
    cfm = float(inp.get("flow_cfm", 20.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "pressure_psi": psi,
        "flow_cfm": cfm,
        "maintenance_status": "certified" if psi < 500 else "high_pressure_check_required"
    }


def analyze_performance(state: State) -> dict[str, Any]:
    """Calculates efficiency metrics based on pressure and flow."""
    psi = state.get("pressure_psi", 0.0)
    cfm = state.get("flow_cfm", 0.0)

    # Mock calculation: efficiency decreases at higher pressures
    efficiency = max(0.0, 1.0 - (psi / 2000.0))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_performance"],
        "efficiency_rating": efficiency
    }


def emit_result(state: State) -> dict[str, Any]:
    """Generates the final compressor capability manifest."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metrics": {
                "psi": state.get("pressure_psi"),
                "cfm": state.get("flow_cfm"),
                "efficiency": state.get("efficiency_rating")
            },
            "status": state.get("maintenance_status"),
            "operational": True
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specs)
_g.add_node("analyze", analyze_performance)
_g.add_node("emit", emit_result)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
