# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172406 — Fuel Tank (segment 25).
Bespoke logic for fuel tank specification validation, safety testing, and certification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172406"
UNISPSC_TITLE = "Fuel Tank"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172406"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Fuel Tank
    tank_capacity_gallons: float
    material_compliance: bool
    pressure_test_passed: bool
    integrity_status: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Inspects the input for fuel tank dimensions and material types."""
    inp = state.get("input") or {}
    capacity = inp.get("capacity", 50.0)
    material = str(inp.get("material", "steel")).lower()

    # Simple compliance logic: must be a recognized industrial material
    compliant = material in ["steel", "aluminum", "alloy", "composite"]

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "tank_capacity_gallons": float(capacity),
        "material_compliance": compliant,
        "integrity_status": "validated",
    }


def perform_pressure_test(state: State) -> dict[str, Any]:
    """Simulates a pressure integrity test based on material compliance."""
    compliant = state.get("material_compliance", False)
    # If material isn't compliant, the test fails safety margins
    test_passed = compliant

    return {
        "log": [f"{UNISPSC_CODE}:perform_pressure_test"],
        "pressure_test_passed": test_passed,
        "integrity_status": "tested_pass" if test_passed else "tested_fail",
    }


def certify_unit(state: State) -> dict[str, Any]:
    """Finalizes the fuel tank actor state and emits certification result."""
    passed = state.get("pressure_test_passed", False)
    capacity = state.get("tank_capacity_gallons", 0.0)
    status = state.get("integrity_status", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:certify_unit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "data": {
                "capacity_gal": capacity,
                "integrity_status": status,
                "certified": passed,
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specifications)
_g.add_node("test", perform_pressure_test)
_g.add_node("certify", certify_unit)

_g.add_edge(START, "validate")
_g.add_edge("validate", "test")
_g.add_edge("test", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
