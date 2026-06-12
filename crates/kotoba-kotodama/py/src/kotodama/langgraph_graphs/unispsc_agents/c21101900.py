# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101900 — Spray (segment 21).

Bespoke LangGraph implementation for agricultural and forestry spraying operations.
This agent manages the validation, parameter calculation, and execution logic
for fluid application workflows across managed land segments.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101900"
UNISPSC_TITLE = "Spray"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101900"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Spraying operations
    fluid_type: str
    target_area_m2: float
    pressure_psi: float
    nozzle_id: str
    safety_check_passed: bool


def validate_readiness(state: State) -> dict[str, Any]:
    """Validate input parameters and equipment readiness for the spraying operation."""
    inp = state.get("input") or {}
    fluid = inp.get("fluid_type", "water")
    area = float(inp.get("target_area_m2", 0.0))

    # Validation logic: Ensure area is positive and fluid is specified
    passed = area > 0 and len(fluid) > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_readiness(area={area}, fluid={fluid})"],
        "fluid_type": fluid,
        "target_area_m2": area,
        "safety_check_passed": passed
    }


def calculate_spray_config(state: State) -> dict[str, Any]:
    """Calculate the required spray pressure and nozzle configuration based on area."""
    area = state.get("target_area_m2", 0.0)

    # Heuristic calculation for pressure requirement
    calc_pressure = 25.0 + (area * 0.02)
    calc_pressure = min(calc_pressure, 80.0)  # Safety cap

    return {
        "log": [f"{UNISPSC_CODE}:calculate_spray_config(pressure={calc_pressure:.2f}PSI)"],
        "pressure_psi": calc_pressure,
        "nozzle_id": "NZ-ISO-04-RED" if calc_pressure > 40 else "NZ-ISO-02-YELLOW"
    }


def execute_application(state: State) -> dict[str, Any]:
    """Simulate the execution of the fluid application process."""
    if not state.get("safety_check_passed"):
        return {"log": [f"{UNISPSC_CODE}:execute_application(ABORTED: validation failed)"]}

    pressure = state.get("pressure_psi", 0.0)
    nozzle = state.get("nozzle_id", "UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:execute_application(Active spray via {nozzle} at {pressure:.1f} PSI)"],
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Generate the final report and telemetry data for the operation."""
    success = state.get("safety_check_passed", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": success,
            "applied_pressure_psi": state.get("pressure_psi"),
            "nozzle_deployed": state.get("nozzle_id"),
            "status": "COMPLETED" if success else "INCOMPLETE"
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_readiness)
_g.add_node("calculate", calculate_spray_config)
_g.add_node("apply", execute_application)
_g.add_node("report", finalize_telemetry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "apply")
_g.add_edge("apply", "report")
_g.add_edge("report", END)

graph = _g.compile()
