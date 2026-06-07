# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25102002 — Vehicle Procurement (segment 25).

Bespoke logic for multi-class vehicle acquisition, fleet optimization
analysis, and safety/emission regulation compliance verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25102002"
UNISPSC_TITLE = "Vehicle Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25102002"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Vehicle Procurement
    fleet_size: int
    vehicle_category: str
    fuel_type: str
    safety_rating: int
    emission_standard_met: bool


def analyze_vehicle_needs(state: State) -> dict[str, Any]:
    """Analyzes procurement request to determine fleet composition and vehicle categories."""
    inp = state.get("input") or {}
    f_size = inp.get("fleet_size", 1)
    category = inp.get("category", "Commercial")
    fuel = inp.get("fuel", "Electric")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_vehicle_needs"],
        "fleet_size": f_size,
        "vehicle_category": category,
        "fuel_type": fuel,
    }


def validate_regulatory_standards(state: State) -> dict[str, Any]:
    """Verifies that the requested vehicles meet regional safety and emission protocols."""
    inp = state.get("input") or {}
    min_safety = inp.get("min_safety_rating", 4)
    # Simulation: Electric vehicles automatically meet high emission standards
    fuel = state.get("fuel_type", "Electric")
    emissions_ok = True if fuel in ["Electric", "Hybrid"] else False

    return {
        "log": [f"{UNISPSC_CODE}:validate_regulatory_standards"],
        "safety_rating": min_safety,
        "emission_standard_met": emissions_ok,
    }


def finalize_vehicle_tender(state: State) -> dict[str, Any]:
    """Compiles the validated requirements into a formal procurement tender document."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_vehicle_tender"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "APPROVED_FOR_TENDER",
            "fleet_details": {
                "size": state.get("fleet_size"),
                "category": state.get("vehicle_category"),
                "fuel": state.get("fuel_type")
            },
            "compliance": {
                "min_safety_rating": state.get("safety_rating"),
                "emission_standards_met": state.get("emission_standard_met")
            },
            "tender_ready": True
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_vehicle_needs)
_g.add_node("validate", validate_regulatory_standards)
_g.add_node("finalize", finalize_vehicle_tender)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "validate")
_g.add_edge("validate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
