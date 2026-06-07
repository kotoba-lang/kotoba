# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111804 — Stationery (segment 14).

Bespoke graph for processing stationery orders, including stock verification
and quality assessment of paper and ink supplies for organizational use.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111804"
UNISPSC_TITLE = "Stationery"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111804"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke Stationery domain fields
    paper_weight_gsm: int
    ink_type: str
    quantity_on_hand: int
    is_customized: bool
    order_status: str


def inventory_lookup(state: State) -> dict[str, Any]:
    """Verify stock availability for the requested stationery items."""
    inp = state.get("input") or {}
    qty = inp.get("quantity", 0)

    # Simulate a lookup in a local inventory registry
    available = 1000  # Hardcoded placeholder for domain logic

    return {
        "log": [f"{UNISPSC_CODE}:inventory_lookup"],
        "quantity_on_hand": available,
        "order_status": "in_stock" if qty <= available else "backordered",
    }


def specification_check(state: State) -> dict[str, Any]:
    """Check if the requested stationery meets quality specifications."""
    inp = state.get("input") or {}
    gsm = inp.get("gsm", 80)
    ink = inp.get("ink", "standard_black")

    return {
        "log": [f"{UNISPSC_CODE}:specification_check"],
        "paper_weight_gsm": gsm,
        "ink_type": ink,
        "is_customized": inp.get("custom_logo", False),
    }


def manifest_generation(state: State) -> dict[str, Any]:
    """Generate the final results and delivery manifest."""
    status = state.get("order_status", "unknown")
    custom = state.get("is_customized", False)

    return {
        "log": [f"{UNISPSC_CODE}:manifest_generation"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "order_status": status,
            "customization_applied": custom,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inventory_lookup", inventory_lookup)
_g.add_node("specification_check", specification_check)
_g.add_node("manifest_generation", manifest_generation)

_g.add_edge(START, "inventory_lookup")
_g.add_edge("inventory_lookup", "specification_check")
_g.add_edge("specification_check", "manifest_generation")
_g.add_edge("manifest_generation", END)

graph = _g.compile()
