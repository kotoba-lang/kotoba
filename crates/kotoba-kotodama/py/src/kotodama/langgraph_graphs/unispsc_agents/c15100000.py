# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15100000 — Supply Chain (segment 15).

Bespoke logic for supply chain management, handling inventory verification,
logistics planning, and order dispatch.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15100000"
UNISPSC_TITLE = "Supply Chain"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15100000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Supply Chain
    inventory_status: str
    route_optimized: bool
    tracking_id: str


def verify_inventory(state: State) -> dict[str, Any]:
    """Verifies that requested supply chain assets are available in the local node."""
    inp = state.get("input") or {}
    # Simple check for items key in input
    has_items = bool(inp.get("items"))
    status = "confirmed" if has_items else "pending_inventory"

    return {
        "log": [f"{UNISPSC_CODE}:verify_inventory:{status}"],
        "inventory_status": status,
    }


def plan_logistics(state: State) -> dict[str, Any]:
    """Simulates route optimization and carrier selection logic."""
    status = state.get("inventory_status")
    can_proceed = (status == "confirmed")

    return {
        "log": [f"{UNISPSC_CODE}:plan_logistics:proceed={can_proceed}"],
        "route_optimized": can_proceed,
    }


def dispatch_order(state: State) -> dict[str, Any]:
    """Finalizes the supply chain flow and issues a tracking identifier."""
    optimized = state.get("route_optimized", False)
    tid = f"SCM-{UNISPSC_CODE}-7788" if optimized else "LOGISTICS_HALTED"

    return {
        "log": [f"{UNISPSC_CODE}:dispatch_order:tid={tid}"],
        "tracking_id": tid,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "tracking_id": tid,
            "ok": optimized,
        },
    }


_g = StateGraph(State)

_g.add_node("verify_inventory", verify_inventory)
_g.add_node("plan_logistics", plan_logistics)
_g.add_node("dispatch_order", dispatch_order)

_g.add_edge(START, "verify_inventory")
_g.add_edge("verify_inventory", "plan_logistics")
_g.add_edge("plan_logistics", "dispatch_order")
_g.add_edge("dispatch_order", END)

graph = _g.compile()
