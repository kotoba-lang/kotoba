# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122216 — Motor Procure (segment 20).

Bespoke logic for the procurement of motors, handling specification
verification, vendor sourcing simulation, and procurement authorization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122216"
UNISPSC_TITLE = "Motor Procure"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122216"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Motor Procure
    motor_specs: dict[str, Any]
    spec_verified: bool
    vendor_id: str
    quote_amount: float
    purchase_authorized: bool


def verify_spec(state: State) -> dict[str, Any]:
    """Validates the motor requirements provided in the input."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})

    # Simple validation: ensure horsepower or voltage is specified
    is_valid = bool(specs.get("horsepower") or specs.get("voltage"))

    return {
        "log": [f"{UNISPSC_CODE}:verify_spec"],
        "motor_specs": specs,
        "spec_verified": is_valid,
    }


def source_vendor(state: State) -> dict[str, Any]:
    """Simulates finding a vendor and obtaining a procurement quote."""
    if not state.get("spec_verified"):
        return {
            "log": [f"{UNISPSC_CODE}:source_vendor_skipped"],
            "vendor_id": "none",
            "quote_amount": 0.0,
        }

    # Mock vendor selection based on segment 20 (Mining/Drilling context)
    specs = state.get("motor_specs", {})
    hp = specs.get("horsepower", 10)

    return {
        "log": [f"{UNISPSC_CODE}:source_vendor"],
        "vendor_id": f"VEND-{UNISPSC_SEGMENT}-001",
        "quote_amount": float(hp * 150.0), # Mock pricing logic
    }


def authorize_purchase(state: State) -> dict[str, Any]:
    """Finalizes the procurement state and prepares the output result."""
    quote = state.get("quote_amount", 0.0)
    authorized = quote > 0 and quote < 50000.0 # Mock limit

    return {
        "log": [f"{UNISPSC_CODE}:authorize_purchase"],
        "purchase_authorized": authorized,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "vendor_id": state.get("vendor_id"),
            "amount": quote,
            "status": "APPROVED" if authorized else "PENDING_REVIEW",
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("verify_spec", verify_spec)
_g.add_node("source_vendor", source_vendor)
_g.add_node("authorize_purchase", authorize_purchase)

_g.add_edge(START, "verify_spec")
_g.add_edge("verify_spec", "source_vendor")
_g.add_edge("source_vendor", "authorize_purchase")
_g.add_edge("authorize_purchase", END)

graph = _g.compile()
