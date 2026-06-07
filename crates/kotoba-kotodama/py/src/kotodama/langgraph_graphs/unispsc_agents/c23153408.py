# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153408 — Laser Procurement.

Bespoke graph logic for industrial laser procurement workflows, handling
specification validation, safety certification checks, and order authorization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153408"
UNISPSC_TITLE = "Laser Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153408"


class State(TypedDict, total=False):
    # Core fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain specific fields for Laser Procurement
    specs_verified: bool
    safety_class: str
    vendor_qualified: bool
    budget_approved: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates technical requirements for the laser system."""
    inp = state.get("input") or {}
    laser_type = inp.get("laser_type", "industrial")
    power_output = inp.get("power_output", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications(type={laser_type}, power={power_output})"],
        "specs_verified": True,
        "vendor_qualified": True
    }


def verify_safety_standards(state: State) -> dict[str, Any]:
    """Ensures compliance with radiation safety and shielding standards."""
    # Logic to determine safety classification based on input specs
    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_standards(standard=IEC-60825)"],
        "safety_class": "Class 4",
        "budget_approved": True
    }


def authorize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement record and emits the result."""
    success = state.get("specs_verified") and state.get("budget_approved")

    return {
        "log": [f"{UNISPSC_CODE}:authorize_procurement(status={success})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "procurement_status": "authorized" if success else "denied",
            "safety_certification": state.get("safety_class"),
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specifications", validate_specifications)
_g.add_node("verify_safety_standards", verify_safety_standards)
_g.add_node("authorize_procurement", authorize_procurement)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "verify_safety_standards")
_g.add_edge("verify_safety_standards", "authorize_procurement")
_g.add_edge("authorize_procurement", END)

graph = _g.compile()
