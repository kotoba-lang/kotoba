# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111801 — Sailboat (segment 25).

Bespoke logic for sailboat maintenance and seaworthiness certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111801"
UNISPSC_TITLE = "Sailboat"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111801"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    hull_inspection_passed: bool
    rigging_certified: bool
    seaworthiness_rating: float


def perform_hull_inspection(state: State) -> dict[str, Any]:
    """Inspects the hull for structural integrity and osmotic blistering."""
    inp = state.get("input") or {}
    hull_condition = inp.get("hull_condition", "excellent")
    passed = hull_condition not in ("damaged", "critical", "leaking")

    return {
        "log": [f"{UNISPSC_CODE}:perform_hull_inspection - status: {hull_condition}"],
        "hull_inspection_passed": passed,
    }


def verify_rigging_system(state: State) -> dict[str, Any]:
    """Checks the mast, standing rigging, and running rigging."""
    inp = state.get("input") or {}
    rigging_age = inp.get("rigging_age_years", 0)
    # Typically rigging should be replaced every 10 years for safety
    certified = rigging_age < 10

    return {
        "log": [f"{UNISPSC_CODE}:verify_rigging_system - age: {rigging_age} years"],
        "rigging_certified": certified,
    }


def finalize_seaworthiness_report(state: State) -> dict[str, Any]:
    """Aggregates inspection results into a final seaworthiness rating."""
    hull_ok = state.get("hull_inspection_passed", False)
    rigging_ok = state.get("rigging_certified", False)

    rating = 0.0
    if hull_ok:
        rating += 0.6
    if rigging_ok:
        rating += 0.4

    status = "Seaworthy" if rating >= 1.0 else "Restricted" if rating >= 0.6 else "Unsafe"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_seaworthiness_report - rating: {rating}"],
        "seaworthiness_rating": rating,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "seaworthiness_status": status,
            "rating": rating,
            "ok": hull_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_hull", perform_hull_inspection)
_g.add_node("verify_rigging", verify_rigging_system)
_g.add_node("finalize", finalize_seaworthiness_report)

_g.add_edge(START, "inspect_hull")
_g.add_edge("inspect_hull", "verify_rigging")
_g.add_edge("verify_rigging", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
