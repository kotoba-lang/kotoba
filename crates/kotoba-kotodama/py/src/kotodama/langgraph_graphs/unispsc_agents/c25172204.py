# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172204 — Truck Door (segment 25).

Bespoke logic for Truck Door manufacturing and compliance verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172204"
UNISPSC_TITLE = "Truck Door"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172204"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra fields for Truck Door domain
    door_specs_verified: bool
    material_check_passed: bool
    locking_mechanism_status: str
    dimensions: dict[str, float]


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates that the input contains necessary truck door specifications."""
    inp = state.get("input") or {}
    dims = inp.get("dimensions", {"height": 0.0, "width": 0.0})
    is_valid = dims.get("height", 0) > 0 and dims.get("width", 0) > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "door_specs_verified": is_valid,
        "dimensions": dims,
    }


def inspect_components(state: State) -> dict[str, Any]:
    """Simulates inspection of materials and locking mechanisms."""
    inp = state.get("input") or {}
    material = str(inp.get("material", "unknown")).lower()
    lock_type = inp.get("lock_type", "manual")

    passed = material in ["steel", "aluminum", "composite"]
    status = "operational" if passed else "failed_inspection"

    return {
        "log": [f"{UNISPSC_CODE}:inspect_components"],
        "material_check_passed": passed,
        "locking_mechanism_status": f"{lock_type}:{status}",
    }


def generate_compliance_report(state: State) -> dict[str, Any]:
    """Finalizes the processing and generates the result dictionary."""
    is_ok = state.get("door_specs_verified", False) and state.get("material_check_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:generate_compliance_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "verification_success": is_ok,
            "locking_status": state.get("locking_mechanism_status"),
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specifications", validate_specifications)
_g.add_node("inspect_components", inspect_components)
_g.add_node("generate_compliance_report", generate_compliance_report)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "inspect_components")
_g.add_edge("inspect_components", "generate_compliance_report")
_g.add_edge("generate_compliance_report", END)

graph = _g.compile()
