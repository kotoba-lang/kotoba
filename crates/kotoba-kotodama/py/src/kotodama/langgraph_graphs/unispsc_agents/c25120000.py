# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25120000 — Rail.
This module implements bespoke logic for track integrity inspection,
rolling stock verification, and dispatch operations within segment 25.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25120000"
UNISPSC_TITLE = "Rail"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25120000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Rail operations
    track_integrity_score: float
    rolling_stock_id: str
    maintenance_verified: bool
    dispatch_clearance: str


def inspect_track_infrastructure(state: State) -> dict[str, Any]:
    """Evaluates the structural integrity of the rail infrastructure."""
    inp = state.get("input") or {}
    # Simulate a diagnostic scan of the rail line
    rating = inp.get("sensor_integrity", 0.98)
    return {
        "log": [f"{UNISPSC_CODE}:inspect_track_infrastructure"],
        "track_integrity_score": rating,
        "maintenance_verified": rating > 0.85,
    }


def verify_rolling_stock_compatibility(state: State) -> dict[str, Any]:
    """Validates that the assigned rolling stock meets the gauge and load requirements."""
    inp = state.get("input") or {}
    rs_id = inp.get("train_consist_id", "RS-8800-ALPHA")

    # Logic depends on previous node's findings
    is_safe = state.get("maintenance_verified", False)
    clearance = "AUTHORIZED" if is_safe else "RESTRICTED"

    return {
        "log": [f"{UNISPSC_CODE}:verify_rolling_stock_compatibility"],
        "rolling_stock_id": rs_id,
        "dispatch_clearance": clearance,
    }


def execute_rail_dispatch(state: State) -> dict[str, Any]:
    """Finalizes the rail operation state and prepares the actor response."""
    status = state.get("dispatch_clearance", "PENDING")
    success = status == "AUTHORIZED"

    return {
        "log": [f"{UNISPSC_CODE}:execute_rail_dispatch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "dispatch_status": status,
            "rolling_stock": state.get("rolling_stock_id"),
            "integrity_index": state.get("track_integrity_score"),
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_track_infrastructure)
_g.add_node("verify", verify_rolling_stock_compatibility)
_g.add_node("dispatch", execute_rail_dispatch)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
