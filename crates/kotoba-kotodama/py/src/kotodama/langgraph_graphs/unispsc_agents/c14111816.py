# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111816 — Stationery (segment 14).

Bespoke graph logic for Stationery inventory and order fulfillment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111816"
UNISPSC_TITLE = "Stationery"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111816"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific stationery fields
    item_catalog: list[str]
    stock_confirmed: bool
    order_quantity: int
    fulfillment_status: str


def inventory_lookup(state: State) -> dict[str, Any]:
    """Check if the requested stationery item exists in the local catalog."""
    inp = state.get("input") or {}
    requested_item = inp.get("item", "generic_paper")
    catalog = ["letterhead", "envelopes", "business_cards", "legal_pads"]

    confirmed = requested_item.lower() in catalog
    return {
        "log": [f"{UNISPSC_CODE}:inventory_lookup:{requested_item}"],
        "item_catalog": catalog,
        "stock_confirmed": confirmed,
    }


def quality_validation(state: State) -> dict[str, Any]:
    """Validate the order quantity and material specs for stationery."""
    inp = state.get("input") or {}
    qty = int(inp.get("quantity", 0))

    valid = qty > 0 and state.get("stock_confirmed", False)
    status = "valid_for_fulfillment" if valid else "validation_failed"

    return {
        "log": [f"{UNISPSC_CODE}:quality_validation:{status}"],
        "order_quantity": qty,
        "fulfillment_status": status,
    }


def manifest_generation(state: State) -> dict[str, Any]:
    """Generate the final result and tracking manifest for the stationery order."""
    status = state.get("fulfillment_status")
    ok = status == "valid_for_fulfillment"

    return {
        "log": [f"{UNISPSC_CODE}:manifest_generation"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "order_details": {
                "quantity": state.get("order_quantity"),
                "status": status,
            },
            "ok": ok,
        },
    }


_g = StateGraph(State)

_g.add_node("inventory_lookup", inventory_lookup)
_g.add_node("quality_validation", quality_validation)
_g.add_node("manifest_generation", manifest_generation)

_g.add_edge(START, "inventory_lookup")
_g.add_edge("inventory_lookup", "quality_validation")
_g.add_edge("quality_validation", "manifest_generation")
_g.add_edge("manifest_generation", END)

graph = _g.compile()
