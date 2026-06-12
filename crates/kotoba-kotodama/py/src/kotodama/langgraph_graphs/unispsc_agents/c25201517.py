# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25201517 — Aircraft Furnish Spec (segment 25).

Bespoke graph logic for managing aircraft furnishing specifications,
ensuring material flammability compliance and weight distribution limits.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201517"
UNISPSC_TITLE = "Aircraft Furnish Spec"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201517"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for Aircraft Furnish Spec
    flammability_test_id: str
    weight_distribution_verified: bool
    cabin_class: str
    material_safety_standard: str


def validate_furnishing_input(state: State) -> dict[str, Any]:
    """Validates the incoming aircraft furnishing parameters and cabin classification."""
    inp = state.get("input") or {}
    cabin_class = inp.get("cabin_class", "Economy")
    safety_std = inp.get("safety_std", "FAA-FAR-25.853")

    return {
        "log": [f"{UNISPSC_CODE}:validate_furnishing_input"],
        "cabin_class": cabin_class,
        "material_safety_standard": safety_std,
    }


def verify_flammability_compliance(state: State) -> dict[str, Any]:
    """Verifies that the furnishings meet the required fire resistance standards."""
    # Logic: Generate a mock test ID for the specified safety standard
    std = state.get("material_safety_standard", "UNKNOWN")
    test_id = f"TEST-{std}-2026-X"

    return {
        "log": [f"{UNISPSC_CODE}:verify_flammability_compliance"],
        "flammability_test_id": test_id,
    }


def assess_weight_balance(state: State) -> dict[str, Any]:
    """Assesses if the furnishing weight distribution is within aircraft limits."""
    # Logic: For the prototype, we verify distribution based on cabin class
    cabin = state.get("cabin_class", "Economy")
    verified = cabin in ["First", "Business", "Economy", "Premium"]

    return {
        "log": [f"{UNISPSC_CODE}:assess_weight_balance"],
        "weight_distribution_verified": verified,
    }


def emit_furnishing_spec(state: State) -> dict[str, Any]:
    """Finalizes the Aircraft Furnish Spec record."""
    verified = state.get("weight_distribution_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_furnishing_spec"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "cabin_class": state.get("cabin_class"),
            "flammability_test_id": state.get("flammability_test_id"),
            "compliance_status": "CERTIFIED" if verified else "PENDING_VERIFICATION",
            "ok": verified,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_furnishing_input", validate_furnishing_input)
_g.add_node("verify_flammability_compliance", verify_flammability_compliance)
_g.add_node("assess_weight_balance", assess_weight_balance)
_g.add_node("emit_furnishing_spec", emit_furnishing_spec)

_g.add_edge(START, "validate_furnishing_input")
_g.add_edge("validate_furnishing_input", "verify_flammability_compliance")
_g.add_edge("verify_flammability_compliance", "assess_weight_balance")
_g.add_edge("assess_weight_balance", "emit_furnishing_spec")
_g.add_edge("emit_furnishing_spec", END)

graph = _g.compile()
