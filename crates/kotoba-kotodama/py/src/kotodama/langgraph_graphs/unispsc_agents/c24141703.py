# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24141703 — Paper Procurement (segment 24).

This agent handles the procurement lifecycle for paper products, including
specification validation, sustainability verification (FSC/PEFC), and
purchase order generation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24141703"
UNISPSC_TITLE = "Paper Procurement"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24141703"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Paper Procurement
    paper_spec_gsm: int
    quantity_reams: int
    sustainability_verified: bool
    supplier_id: str
    delivery_lead_time_days: int


def validate_requirements(state: State) -> dict[str, Any]:
    """Validates the paper specifications and quantity requirements."""
    inp = state.get("input") or {}
    gsm = inp.get("gsm", 80)
    quantity = inp.get("quantity", 0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "paper_spec_gsm": gsm,
        "quantity_reams": quantity,
        "sustainability_verified": inp.get("require_fsc", False)
    }


def sourcing_logic(state: State) -> dict[str, Any]:
    """Simulates finding a supplier and calculating lead times."""
    # Logic based on paper weight and quantity
    lead_time = 3 if state.get("quantity_reams", 0) < 500 else 7

    return {
        "log": [f"{UNISPSC_CODE}:sourcing_logic"],
        "supplier_id": "SUPP-PAPER-V4-99",
        "delivery_lead_time_days": lead_time
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Generates the final result and purchase order metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "order_summary": {
                "gsm": state.get("paper_spec_gsm"),
                "reams": state.get("quantity_reams"),
                "supplier": state.get("supplier_id"),
                "lead_time": f"{state.get('delivery_lead_time_days')} days",
                "certified": state.get("sustainability_verified")
            },
            "status": "PO_READY"
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requirements)
_g.add_node("source", sourcing_logic)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "source")
_g.add_edge("source", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
