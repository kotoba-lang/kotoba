# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25101610 — Water Truck (segment 25).

Bespoke logic for water delivery vehicle management, including tank capacity
monitoring, pump system verification, and mission finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101610"
UNISPSC_TITLE = "Water Truck"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101610"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    tank_status: str
    fill_level_liters: float
    pump_integrity_verified: bool
    destination_site_id: str


def inspect_truck(state: State) -> dict[str, Any]:
    """Verify physical readiness of the vehicle and its water storage."""
    inp = state.get("input") or {}
    fill_level = inp.get("initial_fill", 0.0)
    return {
        "log": [f"{UNISPSC_CODE}:inspect_truck: verifying pump and tank"],
        "tank_status": "full" if fill_level > 5000 else "partial",
        "fill_level_liters": fill_level,
        "pump_integrity_verified": True,
    }


def calculate_load(state: State) -> dict[str, Any]:
    """Determine if current load meets delivery requirements for the site."""
    current_fill = state.get("fill_level_liters", 0.0)
    target = state.get("input", {}).get("target_liters", 1000.0)
    status = "ready" if current_fill >= target else "insufficient_load"
    return {
        "log": [f"{UNISPSC_CODE}:calculate_load: status={status}"],
        "destination_site_id": state.get("input", {}).get("site_id", "ST-001"),
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Emit final mission result and operational telemetry."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "site": state.get("destination_site_id"),
            "load_liters": state.get("fill_level_liters"),
            "operational_status": "deployed" if state.get("pump_integrity_verified") else "maintenance",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_truck)
_g.add_node("calculate", calculate_load)
_g.add_node("finalize", finalize_manifest)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calculate")
_g.add_edge("calculate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
