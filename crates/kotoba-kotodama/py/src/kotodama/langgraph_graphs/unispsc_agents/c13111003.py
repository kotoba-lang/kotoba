# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111003 — Coke Procurement (segment 13).

Bespoke graph logic for industrial coke procurement, handling material
specifications, compliance verification, and order finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111003"
UNISPSC_TITLE = "Coke Procurement"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111003"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Coke Procurement
    coke_type: str
    quantity_mt: float
    sulfur_limit_pct: float
    spec_validated: bool
    compliance_approved: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the grade and volume requirements for the coke shipment."""
    inp = state.get("input") or {}
    coke_type = inp.get("coke_type", "metallurgical")
    quantity = float(inp.get("quantity", 0.0))
    sulfur_limit = float(inp.get("sulfur_limit", 1.0))

    valid = quantity > 0 and sulfur_limit > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs -> {coke_type} ({quantity} MT)"],
        "coke_type": coke_type,
        "quantity_mt": quantity,
        "sulfur_limit_pct": sulfur_limit,
        "spec_validated": valid,
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Checks environmental and purity standards for carbonaceous materials."""
    if not state.get("spec_validated"):
        return {"log": [f"{UNISPSC_CODE}:verify_compliance -> FAILED (invalid specs)"], "compliance_approved": False}

    # Logic: Lower sulfur limits require stricter compliance checks
    sulfur = state.get("sulfur_limit_pct", 1.0)
    approved = sulfur >= 0.5  # Simple business rule simulation

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance -> {'APPROVED' if approved else 'REJECTED'}"],
        "compliance_approved": approved,
    }


def finalize_order(state: State) -> dict[str, Any]:
    """Finalizes the procurement transaction record."""
    ok = state.get("spec_validated", False) and state.get("compliance_approved", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_order"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "procurement_status": "confirmed" if ok else "denied",
            "details": {
                "coke_type": state.get("coke_type"),
                "quantity": state.get("quantity_mt"),
                "sulfur_limit": state.get("sulfur_limit_pct"),
            },
            "ok": ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specs", validate_specs)
_g.add_node("verify_compliance", verify_compliance)
_g.add_node("finalize_order", finalize_order)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "verify_compliance")
_g.add_edge("verify_compliance", "finalize_order")
_g.add_edge("finalize_order", END)

graph = _g.compile()
