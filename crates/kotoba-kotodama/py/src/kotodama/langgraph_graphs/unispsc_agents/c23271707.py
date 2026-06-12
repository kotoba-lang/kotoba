# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23271707 — Weld (segment 23).

Bespoke graph logic for welding process orchestration, covering specification
validation, thermal execution parameters, and quality control inspection.
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271707"
UNISPSC_TITLE = "Weld"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271707"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke welding domain fields
    welding_method: str  # e.g., TIG, MIG, SMAW
    filler_material: str
    heat_input_joules: float
    inspection_passed: bool


def validate_weld_spec(state: State) -> dict[str, Any]:
    """Validates the input parameters for the welding task."""
    inp = state.get("input") or {}
    method = inp.get("method", "GMAW")
    material = inp.get("filler", "ER70S-6")

    return {
        "log": [f"{UNISPSC_CODE}:validate_weld_spec"],
        "welding_method": method,
        "filler_material": material,
    }


def execute_thermal_bond(state: State) -> dict[str, Any]:
    """Simulates the application of heat and filler to create the bond."""
    method = state.get("welding_method", "GMAW")
    # Simulate heat input calculation based on process type
    heat = 1550.0 if method == "GTAW" else 1250.0

    return {
        "log": [f"{UNISPSC_CODE}:execute_thermal_bond"],
        "heat_input_joules": heat,
    }


def verify_integrity(state: State) -> dict[str, Any]:
    """Performs simulated non-destructive testing (NDT) on the joint."""
    heat = state.get("heat_input_joules", 0.0)
    # Simulation: heat must be within tolerance for a sound weld
    passed = 1000.0 <= heat <= 2000.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_integrity"],
        "inspection_passed": passed,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "welding_method": state.get("welding_method"),
            "integrity_verified": passed,
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_weld_spec)
_g.add_node("bond", execute_thermal_bond)
_g.add_node("verify", verify_integrity)

_g.add_edge(START, "validate")
_g.add_edge("validate", "bond")
_g.add_edge("bond", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
