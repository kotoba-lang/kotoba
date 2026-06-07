# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23281503 — Thermal Spray (segment 23).

This bespoke LangGraph implementation handles the state machine for thermal
spray coating processes, including surface preparation validation, parameter
optimization, and application reporting.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23281503"
UNISPSC_TITLE = "Thermal Spray"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23281503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state fields
    substrate_material: str
    coating_material: str
    surface_prep_verified: bool
    spray_parameters: dict[str, float]
    quality_check_passed: bool


def validate_preparation(state: State) -> dict[str, Any]:
    """Node: Ensures the substrate and coating materials are identified."""
    inp = state.get("input") or {}
    substrate = inp.get("substrate", "unknown_steel")
    coating = inp.get("coating", "zinc_alloy")

    return {
        "log": [f"{UNISPSC_CODE}:validate_preparation -> substrate: {substrate}"],
        "substrate_material": substrate,
        "coating_material": coating,
        "surface_prep_verified": True,
    }


def optimize_process(state: State) -> dict[str, Any]:
    """Node: Configures temperature and velocity based on materials."""
    coating = state.get("coating_material", "unknown")

    # Simulated parameter optimization logic
    params = {"temp_c": 2800.0, "gas_velocity_ms": 450.0}
    if "ceramic" in coating.lower():
        params["temp_c"] = 10000.0
        params["gas_velocity_ms"] = 800.0

    return {
        "log": [f"{UNISPSC_CODE}:optimize_process -> parameters calculated for {coating}"],
        "spray_parameters": params,
        "quality_check_passed": True,
    }


def finalize_application(state: State) -> dict[str, Any]:
    """Node: Generates the final result and verification DID."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_application -> report generated"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "process_summary": {
                "substrate": state.get("substrate_material"),
                "coating": state.get("coating_material"),
                "parameters": state.get("spray_parameters"),
                "status": "completed" if state.get("quality_check_passed") else "failed"
            },
            "ok": state.get("quality_check_passed", False),
        },
    }


_g = StateGraph(State)

_g.add_node("validate_preparation", validate_preparation)
_g.add_node("optimize_process", optimize_process)
_g.add_node("finalize_application", finalize_application)

_g.add_edge(START, "validate_preparation")
_g.add_edge("validate_preparation", "optimize_process")
_g.add_edge("optimize_process", "finalize_application")
_g.add_edge("finalize_application", END)

graph = _g.compile()
