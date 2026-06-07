# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111500 — Vessel (segment 25).

Bespoke logic for vessel classification, hull inspection, and safety certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111500"
UNISPSC_TITLE = "Vessel"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for Vessel
    vessel_class: str
    hull_inspection_status: str
    safety_certification: bool
    registry_number: str


def inspect_vessel(state: State) -> dict[str, Any]:
    """Performs initial vessel hull and registry check."""
    inp = state.get("input") or {}
    v_class = inp.get("vessel_class", "unknown")
    reg = inp.get("registry", "UNREGISTERED")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_vessel"],
        "vessel_class": v_class,
        "registry_number": reg,
        "hull_inspection_status": "passed" if reg != "UNREGISTERED" else "failed"
    }


def certify_safety(state: State) -> dict[str, Any]:
    """Verifies safety standards based on hull status and class."""
    hull_ok = state.get("hull_inspection_status") == "passed"
    v_class = state.get("vessel_class")

    # Certification criteria: passed inspection and valid maritime class
    is_valid_class = v_class in ["tanker", "cargo", "passenger", "tug", "research"]
    certified = hull_ok and is_valid_class

    return {
        "log": [f"{UNISPSC_CODE}:certify_safety"],
        "safety_certification": certified
    }


def emit_report(state: State) -> dict[str, Any]:
    """Finalizes the vessel report and emits the result."""
    is_certified = state.get("safety_certification", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "vessel_class": state.get("vessel_class"),
            "status": "CERTIFIED" if is_certified else "INSPECTION_PENDING",
            "registry": state.get("registry_number"),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_vessel", inspect_vessel)
_g.add_node("certify_safety", certify_safety)
_g.add_node("emit_report", emit_report)

_g.add_edge(START, "inspect_vessel")
_g.add_edge("inspect_vessel", "certify_safety")
_g.add_edge("certify_safety", "emit_report")
_g.add_edge("emit_report", END)

graph = _g.compile()
