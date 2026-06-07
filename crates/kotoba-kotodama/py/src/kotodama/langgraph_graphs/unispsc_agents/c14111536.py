# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111536 — Office Supply (segment 14).

Bespoke graph logic for handling office supply procurement and inventory
state transitions. This module is part of the Etz Hayyim UNISPSC agent
corpus, providing domain-specific handling for SKU validation, stock
verification, and fulfillment processing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111536"
UNISPSC_TITLE = "Office Supply"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111536"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    sku_id: str
    order_quantity: int
    stock_available: bool
    requisition_id: str


def validate_order(state: State) -> dict[str, Any]:
    """Extracts and validates the office supply order parameters."""
    inp = state.get("input") or {}
    sku = inp.get("sku", "OFF-GEN-001")
    qty = int(inp.get("quantity", 1))
    req_id = inp.get("req_id", f"REQ-{UNISPSC_CODE}")

    return {
        "log": [f"{UNISPSC_CODE}:validate_order: {sku} (qty: {qty})"],
        "sku_id": sku,
        "order_quantity": qty,
        "requisition_id": req_id
    }


def verify_inventory(state: State) -> dict[str, Any]:
    """Simulates an inventory lookup for the requested office supply SKU."""
    sku = state.get("sku_id")
    # Simple deterministic logic: SKUs containing 'BO' are backordered
    available = "BO" not in sku

    return {
        "log": [f"{UNISPSC_CODE}:verify_inventory: {sku} available={available}"],
        "stock_available": available
    }


def fulfill_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement transaction and generates the result payload."""
    is_available = state.get("stock_available", False)
    sku = state.get("sku_id")
    qty = state.get("order_quantity")
    req_id = state.get("requisition_id")

    status = "fulfilled" if is_available else "backordered"

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "sku": sku,
        "quantity": qty,
        "requisition_id": req_id,
        "status": status,
        "did": UNISPSC_DID,
        "ok": True,
    }

    return {
        "log": [f"{UNISPSC_CODE}:fulfill_procurement: {status}"],
        "result": res
    }


_g = StateGraph(State)

_g.add_node("validate", validate_order)
_g.add_node("inventory", verify_inventory)
_g.add_node("fulfillment", fulfill_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "inventory")
_g.add_edge("inventory", "fulfillment")
_g.add_edge("fulfillment", END)

graph = _g.compile()
