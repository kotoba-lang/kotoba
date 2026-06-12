# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25121702 —  (segment 25).

Bespoke logic for rail vehicle specification, safety inspection, and operational certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25121702"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25121702"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Rail/Vehicle infrastructure
    rolling_stock_id: str
    axle_load_tons: float
    brake_test_verified: bool
    operational_status: str


def register_vehicle(state: State) -> dict[str, Any]:
    """Registers the rail vehicle and defines its basic physical parameters."""
    inp = state.get("input") or {}
    v_id = inp.get("id", "RS-DEFAULT")
    load = inp.get("max_load", 22.5)  # Standard axle load reference

    return {
        "log": [f"{UNISPSC_CODE}:register_vehicle"],
        "rolling_stock_id": v_id,
        "axle_load_tons": load,
    }


def perform_safety_audit(state: State) -> dict[str, Any]:
    """Conducts a simulated brake system and structural integrity audit."""
    load = state.get("axle_load_tons", 0)
    # Safety logic: axle load must be within standard limits for the track
    is_safe = 0 < load <= 25.0

    return {
        "log": [f"{UNISPSC_CODE}:perform_safety_audit"],
        "brake_test_verified": is_safe,
    }


def certify_vehicle(state: State) -> dict[str, Any]:
    """Issues final certification and operational status for the vehicle."""
    is_ready = state.get("brake_test_verified", False)
    status = "COMMISSIONED" if is_ready else "MAINTENANCE_REQUIRED"

    return {
        "log": [f"{UNISPSC_CODE}:certify_vehicle"],
        "operational_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": is_ready,
            "vehicle_manifest": {
                "id": state.get("rolling_stock_id"),
                "load": state.get("axle_load_tons"),
                "status": status
            }
        },
    }


_g = StateGraph(State)

_g.add_node("register", register_vehicle)
_g.add_node("audit", perform_safety_audit)
_g.add_node("certify", certify_vehicle)

_g.add_edge(START, "register")
_g.add_edge("register", "audit")
_g.add_edge("audit", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
