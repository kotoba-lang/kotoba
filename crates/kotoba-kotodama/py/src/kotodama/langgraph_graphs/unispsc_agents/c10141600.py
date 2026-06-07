# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10141600 — Feed Procurement (segment 10).

Bespoke graph logic for procurement of animal feed, focusing on nutritional
compliance, supplier verification, and order execution. This module handles
the transition from requirements validation to order finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10141600"
UNISPSC_TITLE = "Feed Procurement"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10141600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    feed_type: str
    quantity_kg: float
    supplier_id: str
    nutritional_spec_verified: bool
    procurement_status: str


def validate_request(state: State) -> dict[str, Any]:
    """Validates the incoming feed procurement request parameters."""
    inp = state.get("input") or {}
    feed_type = str(inp.get("feed_type", "Standard Grain"))
    quantity = float(inp.get("quantity", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_request"],
        "feed_type": feed_type,
        "quantity_kg": quantity,
        "procurement_status": "validated" if quantity > 0 else "invalid",
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Verifies nutritional specifications and supplier credentials."""
    inp = state.get("input") or {}
    supplier_id = str(inp.get("supplier_id", "VND-BASE-001"))

    # Logic simulation for compliance checking
    is_compliant = state.get("feed_type") != "invalid"

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance"],
        "supplier_id": supplier_id,
        "nutritional_spec_verified": is_compliant,
        "procurement_status": "compliant" if is_compliant else "rejected",
    }


def execute_order(state: State) -> dict[str, Any]:
    """Finalizes the procurement order and emits the result structure."""
    order_id = f"ORDER-{UNISPSC_CODE}-{state.get('supplier_id', 'UNKNOWN')}"

    return {
        "log": [f"{UNISPSC_CODE}:execute_order"],
        "procurement_status": "executed",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "order_id": order_id,
            "feed_type": state.get("feed_type"),
            "quantity_kg": state.get("quantity_kg"),
            "nutritional_verified": state.get("nutritional_spec_verified"),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_request", validate_request)
_g.add_node("verify_compliance", verify_compliance)
_g.add_node("execute_order", execute_order)

_g.add_edge(START, "validate_request")
_g.add_edge("validate_request", "verify_compliance")
_g.add_edge("verify_compliance", "execute_order")
_g.add_edge("execute_order", END)

graph = _g.compile()
