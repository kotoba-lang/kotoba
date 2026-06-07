# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121504"
UNISPSC_TITLE = "Hydraulic"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121504"

class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    pressure_rating_psi: int
    flow_rate_gpm: float
    fluid_type: str
    maintenance_check_passed: bool

def inspect_specifications(state: State) -> dict[str, Any]:
    """Analyzes the initial hydraulic requirements and validates parameters."""
    inp = state.get("input") or {}
    pressure = inp.get("pressure", 3000)
    flow = inp.get("flow", 15.0)
    fluid = inp.get("fluid", "ISO 46")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "pressure_rating_psi": pressure,
        "flow_rate_gpm": flow,
        "fluid_type": fluid,
    }

def simulate_hydraulic_load(state: State) -> dict[str, Any]:
    """Simulates system behavior under the specified pressure and flow conditions."""
    pressure = state.get("pressure_rating_psi", 0)
    # High-pressure systems over 5000 PSI require specific safety certifications
    passed = pressure < 5000

    return {
        "log": [f"{UNISPSC_CODE}:simulate_hydraulic_load"],
        "maintenance_check_passed": passed
    }

def compile_performance_result(state: State) -> dict[str, Any]:
    """Generates the final hydraulic performance report based on simulated data."""
    passed = state.get("maintenance_check_passed", False)
    pressure = state.get("pressure_rating_psi")
    flow = state.get("flow_rate_gpm")
    fluid = state.get("fluid_type")

    return {
        "log": [f"{UNISPSC_CODE}:compile_performance_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "data": {
                "operating_pressure_psi": pressure,
                "operating_flow_gpm": flow,
                "fluid_specification": fluid,
                "safety_clearance": "APPROVED" if passed else "REJECTED_EXCEEDS_RATING"
            },
            "status": "completed"
        }
    }

_g = StateGraph(State)
_g.add_node("inspect", inspect_specifications)
_g.add_node("simulate", simulate_hydraulic_load)
_g.add_node("compile", compile_performance_result)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "simulate")
_g.add_edge("simulate", "compile")
_g.add_edge("compile", END)

graph = _g.compile()
