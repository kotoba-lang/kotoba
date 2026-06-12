# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24102004 — Storage Spec (segment 24).

Bespoke logic for defining and validating storage specifications, including
capacity analysis, environmental requirements, and layout optimization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24102004"
UNISPSC_TITLE = "Storage Spec"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24102004"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for Storage Spec
    capacity_verified: bool
    environmental_reqs_met: bool
    optimized_layout: dict[str, Any]


def analyze_requirements(state: State) -> dict[str, Any]:
    """Analyzes physical storage requirements from input."""
    inp = state.get("input") or {}
    dims = inp.get("dimensions", {})
    weight = inp.get("weight_limit", 0)

    # Verify capacity based on provided physical constraints
    verified = weight > 0 and bool(dims)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_requirements"],
        "capacity_verified": verified,
    }


def check_environmental_constraints(state: State) -> dict[str, Any]:
    """Evaluates environmental factors like temperature or hazardous containment."""
    inp = state.get("input") or {}
    hazard = inp.get("hazardous_material", False)
    containment = inp.get("containment_certified", False)

    # Requirement: Hazardous materials must have containment certification
    reqs_met = not hazard or containment

    return {
        "log": [f"{UNISPSC_CODE}:check_environmental_constraints"],
        "environmental_reqs_met": reqs_met,
    }


def finalize_storage_spec(state: State) -> dict[str, Any]:
    """Consolidates verified requirements into a final specification."""
    cap = state.get("capacity_verified", False)
    env = state.get("environmental_reqs_met", False)

    # Mock layout optimization logic
    layout = {
        "aisle_width_meters": 3.2,
        "rack_configuration": "high-density" if cap else "standard",
        "safety_factor": 1.25 if env else 1.0
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_storage_spec"],
        "optimized_layout": layout,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification_valid": cap and env,
            "layout_metadata": layout,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_requirements", analyze_requirements)
_g.add_node("check_environmental_constraints", check_environmental_constraints)
_g.add_node("finalize_storage_spec", finalize_storage_spec)

_g.add_edge(START, "analyze_requirements")
_g.add_edge("analyze_requirements", "check_environmental_constraints")
_g.add_edge("check_environmental_constraints", "finalize_storage_spec")
_g.add_edge("finalize_storage_spec", END)

graph = _g.compile()
