# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24102009 — Rail Spec.

Bespoke graph logic for validating and processing railway material handling
specifications, ensuring adherence to gauge and load safety standards.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24102009"
UNISPSC_TITLE = "Rail Spec"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24102009"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Rail Spec
    gauge_mm: int
    max_load_kn: float
    material_compliance: bool
    safety_factor: float


def validate_engineering_specs(state: State) -> dict[str, Any]:
    """Validates the physical dimensions and load tolerances of the rail spec."""
    inp = state.get("input") or {}
    gauge = inp.get("gauge_mm", 1435)  # Default to standard gauge (1435mm)
    load = float(inp.get("max_load_kn", 0.0))

    # Validation against common international rail gauges
    valid_gauge = gauge in [1067, 1435, 1524, 1676]
    valid_load = load > 0 and load <= 1000.0

    return {
        "log": [f"{UNISPSC_CODE}:validate: gauge={gauge}, load={load}"],
        "gauge_mm": gauge,
        "max_load_kn": load,
        "material_compliance": valid_gauge and valid_load,
    }


def compute_safety_thresholds(state: State) -> dict[str, Any]:
    """Calculates safety factors based on validated engineering data."""
    load = state.get("max_load_kn", 0.0)
    compliance = state.get("material_compliance", False)

    # Calculate safety factor based on load density and compliance status
    safety_factor = 1.5 if compliance else 0.0
    if load > 500:
        safety_factor -= 0.1  # Heavier loads reduce the safety margin if not reinforced

    return {
        "log": [f"{UNISPSC_CODE}:analyze: safety_factor={safety_factor}"],
        "safety_factor": safety_factor,
    }


def finalize_rail_specification(state: State) -> dict[str, Any]:
    """Emits the final processed rail specification record and certification status."""
    compliance = state.get("material_compliance", False)
    safety = state.get("safety_factor", 0.0)

    is_approved = compliance and safety >= 1.2

    return {
        "log": [f"{UNISPSC_CODE}:finalize: approved={is_approved}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "CERTIFIED" if is_approved else "FAILED_INSPECTION",
            "metrics": {
                "gauge": state.get("gauge_mm"),
                "load_kn": state.get("max_load_kn"),
                "safety_index": safety,
            },
            "ok": is_approved,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_engineering_specs)
_g.add_node("analyze", compute_safety_thresholds)
_g.add_node("finalize", finalize_rail_specification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
