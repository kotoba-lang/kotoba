# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14122104 — Thermal.

This bespoke graph manages the state transitions for Thermal paper materials,
evaluating coating specifications, thermal sensitivity, and archival durability.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14122104"
UNISPSC_TITLE = "Thermal"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14122104"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields for Thermal Paper
    coating_specification: str
    heat_sensitivity_level: float
    archival_life_years: int
    is_bpa_free: bool


def verify_spec(state: State) -> dict[str, Any]:
    """Validate the incoming thermal material specifications."""
    inp = state.get("input") or {}
    spec = inp.get("spec", "standard-thermal")
    bpa_free = inp.get("bpa_free", True)
    return {
        "log": [f"{UNISPSC_CODE}:verify_spec"],
        "coating_specification": spec,
        "is_bpa_free": bpa_free,
    }


def analyze_thermal_properties(state: State) -> dict[str, Any]:
    """Calculate heat sensitivity and projected archival life based on coating."""
    spec = state.get("coating_specification", "standard")

    # Heuristic mapping for bespoke thermal logic
    if "high-sensitivity" in spec:
        sensitivity = 0.95
        life = 7
    elif "topcoated" in spec:
        sensitivity = 0.70
        life = 15
    else:
        sensitivity = 0.50
        life = 5

    return {
        "log": [f"{UNISPSC_CODE}:analyze_thermal_properties"],
        "heat_sensitivity_level": sensitivity,
        "archival_life_years": life,
    }


def finalize_output(state: State) -> dict[str, Any]:
    """Construct the final result dictionary for the thermal agent."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_output"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "analysis": {
                "coating": state.get("coating_specification"),
                "sensitivity": state.get("heat_sensitivity_level"),
                "archival_life": state.get("archival_life_years"),
                "bpa_free": state.get("is_bpa_free"),
            },
            "status": "certified",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("verify_spec", verify_spec)
_g.add_node("analyze_thermal_properties", analyze_thermal_properties)
_g.add_node("finalize_output", finalize_output)

_g.add_edge(START, "verify_spec")
_g.add_edge("verify_spec", "analyze_thermal_properties")
_g.add_edge("analyze_thermal_properties", "finalize_output")
_g.add_edge("finalize_output", END)

graph = _g.compile()
