# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15121525 — Metal Procure (segment 15).

Bespoke logic for metal procurement processes including alloy verification,
tonnage assessment, and quality certification checks.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15121525"
UNISPSC_TITLE = "Metal Procure"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15121525"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Metal Procure
    alloy_specification: str
    tonnage_requested: float
    supplier_id: str
    quality_certification_required: bool
    procurement_approved: bool


def validate_procurement(state: State) -> dict[str, Any]:
    """Validates the procurement request against metal specifications."""
    inp = state.get("input") or {}
    alloy = str(inp.get("alloy", "Standard Steel"))
    tonnage = float(inp.get("tonnage", 0.0))
    supplier = str(inp.get("supplier_id", "VND-001"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_procurement -> {alloy} ({tonnage}t) from {supplier}"],
        "alloy_specification": alloy,
        "tonnage_requested": tonnage,
        "supplier_id": supplier,
        "quality_certification_required": tonnage > 10.0
    }


def assess_inventory(state: State) -> dict[str, Any]:
    """Simulates inventory check for the requested metal procurement."""
    tonnage = state.get("tonnage_requested", 0.0)
    # Automated approval for reasonable quantities; larger orders require manual review simulation
    approved = 0.0 < tonnage < 1000.0

    return {
        "log": [f"{UNISPSC_CODE}:assess_inventory -> approved: {approved}"],
        "procurement_approved": approved
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement record and emits the result."""
    approved = state.get("procurement_approved", False)
    alloy = state.get("alloy_specification")
    tonnage = state.get("tonnage_requested")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "COMPLETED" if approved else "REJECTED_OR_PENDING",
            "details": {
                "alloy": alloy,
                "tonnage": tonnage,
                "certification_required": state.get("quality_certification_required")
            },
            "ok": approved,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_procurement", validate_procurement)
_g.add_node("assess_inventory", assess_inventory)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_procurement")
_g.add_edge("validate_procurement", "assess_inventory")
_g.add_edge("assess_inventory", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
