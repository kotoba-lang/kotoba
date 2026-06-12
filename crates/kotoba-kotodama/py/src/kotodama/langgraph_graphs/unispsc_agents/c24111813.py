# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24111813 — Rinse Tank (segment 24).

Bespoke logic for industrial rinse tank operations including pressure validation,
automated rinse sequences, and operational state reporting.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24111813"
UNISPSC_TITLE = "Rinse Tank"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24111813"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain state for Rinse Tank
    fluid_composition: str
    target_pressure_psi: float
    drain_status: str
    cycle_complete: bool


def validate_parameters(state: State) -> dict[str, Any]:
    """Validates input parameters for the rinse operation."""
    inp = state.get("input") or {}
    fluid = inp.get("fluid", "deionized_water")
    pressure = float(inp.get("pressure", 45.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters -> fluid={fluid}, pressure={pressure}psi"],
        "fluid_composition": fluid,
        "target_pressure_psi": pressure,
        "drain_status": "closed",
    }


def execute_rinse(state: State) -> dict[str, Any]:
    """Simulates the rinsing cycle based on validated parameters."""
    pressure = state.get("target_pressure_psi", 0.0)
    is_nominal = 30.0 <= pressure <= 60.0

    return {
        "log": [f"{UNISPSC_CODE}:execute_rinse -> pressure_ok={is_nominal}"],
        "cycle_complete": is_nominal,
        "drain_status": "opening" if is_nominal else "closed",
    }


def finalize_process(state: State) -> dict[str, Any]:
    """Finalizes the rinse tank state and compiles the result metadata."""
    success = state.get("cycle_complete", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_process -> complete={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "success" if success else "fault",
            "telemetry": {
                "fluid": state.get("fluid_composition"),
                "pressure": state.get("target_pressure_psi"),
                "drain": "vented" if success else "sealed"
            },
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_parameters)
_g.add_node("rinse", execute_rinse)
_g.add_node("finalize", finalize_process)

_g.add_edge(START, "validate")
_g.add_edge("validate", "rinse")
_g.add_edge("rinse", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
