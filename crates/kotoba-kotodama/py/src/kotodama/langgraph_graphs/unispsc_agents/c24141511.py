# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24141511 — Load Binder (segment 24).

Bespoke implementation for Load Binder management, ensuring mechanical integrity,
tension calibration, and safety compliance for heavy-duty cargo securing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24141511"
UNISPSC_TITLE = "Load Binder"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24141511"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Load Binder
    binder_type: str  # e.g., "ratchet", "lever"
    tension_rating_lbs: int
    chain_size_inches: str
    safety_latch_status: bool
    load_integrity_verified: bool


def inspect_hardware(state: State) -> dict[str, Any]:
    """Validates the physical specifications of the load binder equipment."""
    inp = state.get("input") or {}
    b_type = inp.get("type", "ratchet")
    rating = inp.get("rating", 6600)
    size = inp.get("chain_size", "5/16-3/8")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_hardware"],
        "binder_type": b_type,
        "tension_rating_lbs": rating,
        "chain_size_inches": size,
    }


def calibrate_tension(state: State) -> dict[str, Any]:
    """Simulates the application of tension and safety latch engagement."""
    # Logic: Ratchet binders generally have higher safety control than lever binders
    is_ratchet = state.get("binder_type") == "ratchet"
    latch_engaged = True if is_ratchet else False

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_tension"],
        "safety_latch_status": latch_engaged,
    }


def verify_securing(state: State) -> dict[str, Any]:
    """Final verification of the load securing state and result emission."""
    latch = state.get("safety_latch_status", False)
    rating = state.get("tension_rating_lbs", 0)

    # Verified if latch is engaged and rating is sufficient
    verified = latch and rating >= 5400

    return {
        "log": [f"{UNISPSC_CODE}:verify_securing"],
        "load_integrity_verified": verified,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "SECURED" if verified else "WARNING_UNSECURED",
            "metadata": {
                "did": UNISPSC_DID,
                "segment": UNISPSC_SEGMENT,
                "binder_specs": {
                    "type": state.get("binder_type"),
                    "rating": rating,
                    "chain": state.get("chain_size_inches")
                }
            },
            "ok": verified,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_hardware", inspect_hardware)
_g.add_node("calibrate_tension", calibrate_tension)
_g.add_node("verify_securing", verify_securing)

_g.add_edge(START, "inspect_hardware")
_g.add_edge("inspect_hardware", "calibrate_tension")
_g.add_edge("calibrate_tension", "verify_securing")
_g.add_edge("verify_securing", END)

graph = _g.compile()
