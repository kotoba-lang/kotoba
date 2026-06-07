# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172007 — Strut Procurement (segment 25).

Bespoke graph logic for the procurement and verification of structural struts.
This agent handles specification validation, supplier selection, and delivery scheduling.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172007"
UNISPSC_TITLE = "Strut Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172007"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific strut procurement state
    spec_verified: bool
    supplier_id: str
    inventory_available: int
    delivery_window: str


def validate_spec(state: State) -> dict[str, Any]:
    """Validates structural requirements for the requested struts."""
    inp = state.get("input") or {}
    spec = inp.get("specification", {})
    # Check for mandatory strut attributes like length and load capacity
    has_length = "length" in spec
    has_capacity = "load_capacity" in spec
    is_valid = has_length and has_capacity

    return {
        "log": [f"{UNISPSC_CODE}:validate_spec: valid={is_valid}"],
        "spec_verified": is_valid,
    }


def inventory_lookup(state: State) -> dict[str, Any]:
    """Checks regional supplier inventory for compliant components."""
    # Simulate inventory search logic based on domain parameters
    return {
        "log": [f"{UNISPSC_CODE}:inventory_lookup: checking regional warehouses"],
        "inventory_available": 1500,
        "supplier_id": "VEND-STRUT-X9",
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Generates the procurement result with delivery details."""
    is_ok = state.get("spec_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "delivery_window": "3-5 business days",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_status": "authorized" if is_ok else "rejected",
            "vendor": state.get("supplier_id"),
            "available_units": state.get("inventory_available"),
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_spec", validate_spec)
_g.add_node("inventory_lookup", inventory_lookup)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_spec")
_g.add_edge("validate_spec", "inventory_lookup")
_g.add_edge("inventory_lookup", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
