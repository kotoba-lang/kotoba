# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101906 — Tractor Parts (segment 21).

Bespoke graph logic for managing tractor component inventory and compatibility verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101906"
UNISPSC_TITLE = "Tractor Parts"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101906"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    part_spec_id: str
    compatibility_verified: bool
    inventory_available: bool
    shipping_status: str


def inspect_part(state: State) -> dict[str, Any]:
    """Inspects the part specification from the input."""
    inp = state.get("input") or {}
    spec_id = inp.get("part_id", "UNKNOWN-000")
    # Simulate compatibility check logic: TRAC prefix required for valid parts
    verified = str(spec_id).startswith("TRAC")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_part:{spec_id}"],
        "part_spec_id": spec_id,
        "compatibility_verified": verified,
    }


def verify_inventory(state: State) -> dict[str, Any]:
    """Checks if the inspected part is available in the regional warehouse."""
    spec_id = state.get("part_spec_id", "N/A")
    # Simulate inventory lookup: parts with specific naming length are in stock
    available = len(str(spec_id)) > 6
    return {
        "log": [f"{UNISPSC_CODE}:verify_inventory:{available}"],
        "inventory_available": available,
    }


def package_and_ship(state: State) -> dict[str, Any]:
    """Finalizes the fulfillment process and sets the result."""
    is_compatible = state.get("compatibility_verified", False)
    is_available = state.get("inventory_available", False)

    ok = is_compatible and is_available
    status = "SHIPPED" if ok else "REJECTED_INCOMPATIBLE_OR_OUT_OF_STOCK"

    return {
        "log": [f"{UNISPSC_CODE}:package_and_ship:{status}"],
        "shipping_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "part_id": state.get("part_spec_id"),
            "shipping_status": status,
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_part", inspect_part)
_g.add_node("verify_inventory", verify_inventory)
_g.add_node("package_and_ship", package_and_ship)

_g.add_edge(START, "inspect_part")
_g.add_edge("inspect_part", "verify_inventory")
_g.add_edge("verify_inventory", "package_and_ship")
_g.add_edge("package_and_ship", END)

graph = _g.compile()
