# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172504 — Tire (segment 25).

Bespoke graph logic for tire specification validation and inventory processing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172504"
UNISPSC_TITLE = "Tire"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172504"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain specific fields for "Tire"
    tire_category: str  # e.g., Passenger, Commercial, Off-Road
    safety_rating_verified: bool
    tread_depth_check: str
    inventory_lot: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Inspects the input specs for pressure ratings and tread depth."""
    inp = state.get("input") or {}
    tread = inp.get("tread_depth", 0)

    status = "Fail" if tread < 1.6 else "Pass"

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "tread_depth_check": status,
        "safety_rating_verified": inp.get("safety_cert", False)
    }


def categorize_tire(state: State) -> dict[str, Any]:
    """Assigns a category based on the load index or dimensions."""
    inp = state.get("input") or {}
    load_index = inp.get("load_index", 0)

    category = "Passenger"
    if load_index > 120:
        category = "Commercial"
    elif inp.get("terrain") == "all-terrain":
        category = "Off-Road"

    return {
        "log": [f"{UNISPSC_CODE}:categorize_tire"],
        "tire_category": category,
        "inventory_lot": f"LOT-{category[:3].upper()}-{UNISPSC_CODE[-4:]}"
    }


def finalize_asset_record(state: State) -> dict[str, Any]:
    """Compiles the final tire asset metadata."""
    is_ok = state.get("safety_rating_verified", False) and state.get("tread_depth_check") == "Pass"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "category": state.get("tire_category"),
            "lot": state.get("inventory_lot"),
            "compliance": {
                "safety_verified": state.get("safety_rating_verified"),
                "tread_status": state.get("tread_depth_check")
            },
            "did": UNISPSC_DID,
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("categorize", categorize_tire)
_g.add_node("finalize", finalize_asset_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "categorize")
_g.add_edge("categorize", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
