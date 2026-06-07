# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14121800 — Paper Procurement.

This agent handles the procurement lifecycle for paper materials, including
specification validation, inventory availability checks, and order finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14121800"
UNISPSC_TITLE = "Paper Procurement"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14121800"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Paper Procurement
    specifications_verified: bool
    stock_level_id: str
    sustainability_certified: bool
    procurement_status: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates paper weight (GSM), dimensions, and finish requirements."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})
    # Mock validation logic for paper specs
    is_valid = specs.get("gsm", 0) > 0 and "size" in specs
    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "specifications_verified": is_valid,
        "sustainability_certified": specs.get("recycled", False),
    }


def check_inventory(state: State) -> dict[str, Any]:
    """Checks regional stock levels for the requested paper products."""
    if not state.get("specifications_verified"):
        return {
            "log": [f"{UNISPSC_CODE}:check_inventory_skipped"],
            "procurement_status": "rejected_specs",
        }

    # Simulate inventory lookup
    return {
        "log": [f"{UNISPSC_CODE}:check_inventory"],
        "stock_level_id": "WH-PAPER-001-ALPHA",
        "procurement_status": "in_stock",
    }


def finalize_order(state: State) -> dict[str, Any]:
    """Finalizes the procurement request and emits the transaction record."""
    status = state.get("procurement_status", "unknown")
    success = status == "in_stock"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_order"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "order_id": "REQ-14121800-2026-X1",
            "stock_location": state.get("stock_level_id"),
            "certified": state.get("sustainability_certified", False),
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("inventory", check_inventory)
_g.add_node("finalize", finalize_order)

_g.add_edge(START, "validate")
_g.add_edge("validate", "inventory")
_g.add_edge("inventory", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
