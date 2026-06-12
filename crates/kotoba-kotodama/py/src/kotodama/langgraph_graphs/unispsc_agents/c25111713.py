# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111713 — Fleet Oiler (segment 25).
Maritime refueling and replenishment logistics agent for Underway Replenishment (UNREP).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111713"
UNISPSC_TITLE = "Fleet Oiler"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111713"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain state for a Fleet Oiler
    target_vessel_id: str
    fuel_transfer_volume: float
    safety_buffer_verified: bool
    sea_state_advisory: int


def inspect_manifest(state: State) -> dict[str, Any]:
    """Verify target vessel and sea conditions before commencing replenishment."""
    inp = state.get("input") or {}
    vessel = inp.get("target_vessel", "USS-DEFAULT-REPLENISH")
    sea_state = inp.get("sea_state", 3)

    # Operations are generally safe up to Sea State 5
    safe = sea_state <= 5

    return {
        "log": [f"{UNISPSC_CODE}:inspect_manifest -> target:{vessel} sea_state:{sea_state}"],
        "target_vessel_id": vessel,
        "sea_state_advisory": sea_state,
        "safety_buffer_verified": safe
    }


def transfer_liquids(state: State) -> dict[str, Any]:
    """Execute the fuel transfer process via replenishment stations."""
    if not state.get("safety_buffer_verified"):
        return {"log": [f"{UNISPSC_CODE}:transfer_liquids -> ABORTED (Safety violation)"]}

    requested_qty = state.get("input", {}).get("fuel_qty_liters", 50000.0)
    return {
        "log": [f"{UNISPSC_CODE}:transfer_liquids -> {requested_qty}L delivered"],
        "fuel_transfer_volume": requested_qty
    }


def finalize_unrep(state: State) -> dict[str, Any]:
    """Secure all lines and generate the replenishment summary report."""
    success = state.get("safety_buffer_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_unrep -> cleanup complete"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "SUCCESS" if success else "ABORTED",
            "vessel": state.get("target_vessel_id"),
            "total_delivered": state.get("fuel_transfer_volume", 0.0) if success else 0.0,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_manifest", inspect_manifest)
_g.add_node("transfer_liquids", transfer_liquids)
_g.add_node("finalize_unrep", finalize_unrep)

_g.add_edge(START, "inspect_manifest")
_g.add_edge("inspect_manifest", "transfer_liquids")
_g.add_edge("transfer_liquids", "finalize_unrep")
_g.add_edge("finalize_unrep", END)

graph = _g.compile()
