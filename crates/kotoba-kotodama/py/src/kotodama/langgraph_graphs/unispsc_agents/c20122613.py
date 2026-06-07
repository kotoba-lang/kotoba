# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122613 — Robot Procurement (segment 20).

Bespoke graph logic for managing the procurement lifecycle of industrial
and service robots, including requirement validation and vendor assessment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122613"
UNISPSC_TITLE = "Robot Procurement"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122613"


class State(TypedDict, total=False):
    # Required core fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Bespoke domain fields for Robot Procurement
    specs_verified: bool
    vendor_assessment: str
    budget_limit: float
    procurement_status: str


def verify_requirements(state: State) -> dict[str, Any]:
    """Validates the robot specifications and budget constraints from input."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})
    budget = inp.get("budget", 0.0)

    # Simple validation logic: require specs and a positive budget
    is_valid = bool(specs) and budget > 0
    status = "REQUISITION_VERIFIED" if is_valid else "REQUISITION_FAILED"

    return {
        "log": [f"{UNISPSC_CODE}:verify_requirements -> {status}"],
        "specs_verified": is_valid,
        "budget_limit": budget,
        "procurement_status": status,
    }


def assess_vendors(state: State) -> dict[str, Any]:
    """Simulates the selection of a robotics vendor based on verified specs."""
    if not state.get("specs_verified"):
        return {
            "log": [f"{UNISPSC_CODE}:assess_vendors -> SKIPPED (INVALID SPECS)"],
            "vendor_assessment": "NONE",
            "procurement_status": "VENDOR_ASSESSMENT_SKIPPED",
        }

    # Deterministic mock vendor selection
    vendor_id = "VND-ROBO-AUTO-77"
    return {
        "log": [f"{UNISPSC_CODE}:assess_vendors -> SELECTED {vendor_id}"],
        "vendor_assessment": vendor_id,
        "procurement_status": "VENDOR_SELECTED",
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement state and emits the structured result."""
    is_ok = state.get("specs_verified", False) and state.get("vendor_assessment") != "NONE"
    final_status = "COMPLETED" if is_ok else "TERMINATED_ERROR"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement -> {final_status}"],
        "procurement_status": final_status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_id": f"PR-{UNISPSC_CODE}-2026-X",
            "selected_vendor": state.get("vendor_assessment"),
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

# Define the processing pipeline
_g.add_node("verify_requirements", verify_requirements)
_g.add_node("assess_vendors", assess_vendors)
_g.add_node("finalize_procurement", finalize_procurement)

# Build the execution flow
_g.add_edge(START, "verify_requirements")
_g.add_edge("verify_requirements", "assess_vendors")
_g.add_edge("assess_vendors", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

# Export the compiled graph for the executor cell
graph = _g.compile()
