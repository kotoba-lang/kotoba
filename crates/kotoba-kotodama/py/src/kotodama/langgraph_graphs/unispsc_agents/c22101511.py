# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101511 — Machine Spec (segment 22).

This bespoke implementation handles technical specification validation,
operational compatibility assessment, and technical report generation for
machinery and heavy equipment within the Etz Hayyim framework.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101511"
UNISPSC_TITLE = "Machine Spec"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101511"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Machine Spec
    geometry_verified: bool
    power_specs_compliant: bool
    mechanical_fit_status: str
    tolerance_check_passed: bool


def validate_geometric_constraints(state: State) -> dict[str, Any]:
    """Verify that physical dimensions and mounting points are specified."""
    inp = state.get("input") or {}
    dims = inp.get("dimensions", {})
    is_valid = all(k in dims for k in ["height", "width", "depth"])

    return {
        "log": [f"{UNISPSC_CODE}:validate_geometric_constraints"],
        "geometry_verified": is_valid,
        "tolerance_check_passed": inp.get("precision_grade") == "A"
    }


def analyze_operational_compatibility(state: State) -> dict[str, Any]:
    """Assess power draw and mechanical interface requirements."""
    inp = state.get("input") or {}
    power = inp.get("power_spec", {})

    # Simulate checking voltage and phase compliance
    has_power_data = bool(power.get("voltage"))
    interface_match = "ISO" in inp.get("interface_standard", "")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_operational_compatibility"],
        "power_specs_compliant": has_power_data,
        "mechanical_fit_status": "optimal" if interface_match else "generic"
    }


def finalize_technical_specification(state: State) -> dict[str, Any]:
    """Compile the final machine specification record."""
    is_ok = state.get("geometry_verified") and state.get("power_specs_compliant")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_technical_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "verification_summary": {
                "geometry": "Verified" if state.get("geometry_verified") else "Incomplete",
                "power": "Compliant" if state.get("power_specs_compliant") else "Pending",
                "fit": state.get("mechanical_fit_status")
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_geometry", validate_geometric_constraints)
_g.add_node("analyze_compatibility", analyze_operational_compatibility)
_g.add_node("finalize_spec", finalize_technical_specification)

_g.add_edge(START, "validate_geometry")
_g.add_edge("validate_geometry", "analyze_compatibility")
_g.add_edge("analyze_compatibility", "finalize_spec")
_g.add_edge("finalize_spec", END)

graph = _g.compile()
