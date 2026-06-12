# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111700 — Paper Procurement (segment 14).

Bespoke graph logic for paper requisition, sustainability verification,
and procurement finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111700"
UNISPSC_TITLE = "Paper Procurement"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111700"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state fields for Paper Procurement
    requisition_valid: bool
    sustainability_verified: bool
    vendor_assignment: str
    order_quantity_reams: int
    paper_specification: str


def verify_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming paper procurement request and specifications."""
    inp = state.get("input") or {}
    qty = inp.get("quantity", 0)
    spec = inp.get("specification", "Standard A4 80gsm")

    is_valid = qty > 0
    return {
        "log": [f"{UNISPSC_CODE}:verify_requisition"],
        "requisition_valid": is_valid,
        "order_quantity_reams": qty,
        "paper_specification": spec,
    }


def check_sustainability(state: State) -> dict[str, Any]:
    """Ensures the paper source meets environmental and FSC standards."""
    inp = state.get("input") or {}
    # Assume procurement policy requires recycled content or FSC certification
    is_fsc = inp.get("fsc_certified", False)
    recycled_pct = inp.get("recycled_content_pct", 0)

    verified = is_fsc or recycled_pct >= 30
    vendor = "EcoPaper-Solutions-Ltd" if verified else "General-Office-Wholesale"

    return {
        "log": [f"{UNISPSC_CODE}:check_sustainability"],
        "sustainability_verified": verified,
        "vendor_assignment": vendor,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Compiles the procurement order and prepares the final result."""
    success = state.get("requisition_valid", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "ordered" if success else "failed",
            "procurement_data": {
                "vendor": state.get("vendor_assignment"),
                "quantity": state.get("order_quantity_reams"),
                "spec": state.get("paper_specification"),
                "eco_compliant": state.get("sustainability_verified"),
            },
        },
    }


_g = StateGraph(State)

_g.add_node("verify_requisition", verify_requisition)
_g.add_node("check_sustainability", check_sustainability)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "verify_requisition")
_g.add_edge("verify_requisition", "check_sustainability")
_g.add_edge("check_sustainability", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
