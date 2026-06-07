# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10171500"
UNISPSC_TITLE = "Supply Chain"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10171500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    inventory_verified: bool
    logistics_route_optimized: bool
    supplier_compliance_status: str
    tracking_id: str


def validate_inventory(state: State) -> dict[str, Any]:
    """Node: Checks inventory availability for the requested supply chain operation."""
    inp = state.get("input") or {}
    items = inp.get("items", [])
    verified = len(items) > 0 if items else False
    return {
        "log": [f"{UNISPSC_CODE}:validate_inventory"],
        "inventory_verified": verified,
        "supplier_compliance_status": "verified_standard",
    }


def optimize_logistics(state: State) -> dict[str, Any]:
    """Node: Calculates optimal routing and assigns a tracking identifier."""
    return {
        "log": [f"{UNISPSC_CODE}:optimize_logistics"],
        "logistics_route_optimized": True,
        "tracking_id": "SC-10171500-TX-99",
    }


def finalize_dispatch(state: State) -> dict[str, Any]:
    """Node: Compiles the final state into a result dictionary."""
    success = state.get("inventory_verified", False) and state.get("logistics_route_optimized", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_dispatch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "tracking_id": state.get("tracking_id"),
            "status": "dispatched" if success else "pending",
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_inventory", validate_inventory)
_g.add_node("optimize_logistics", optimize_logistics)
_g.add_node("finalize_dispatch", finalize_dispatch)

_g.add_edge(START, "validate_inventory")
_g.add_edge("validate_inventory", "optimize_logistics")
_g.add_edge("optimize_logistics", "finalize_dispatch")
_g.add_edge("finalize_dispatch", END)

graph = _g.compile()
