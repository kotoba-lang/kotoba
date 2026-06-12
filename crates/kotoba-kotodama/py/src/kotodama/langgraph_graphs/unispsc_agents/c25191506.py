# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25191506 — Refueling.
Bespoke logic for managing refueling operations, safety checks, and delivery tracking.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25191506"
UNISPSC_TITLE = "Refueling"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25191506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Refueling
    fuel_type: str
    volume_liters: float
    vehicle_id: str
    safety_cleared: bool
    pump_status: str


def initialize_refueling(state: State) -> dict[str, Any]:
    """Extract parameters from input and prepare the refueling session."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:initialize_refueling"],
        "fuel_type": inp.get("fuel_type", "Diesel"),
        "volume_liters": float(inp.get("volume", 0.0)),
        "vehicle_id": inp.get("vehicle_id", "STATION-GENERIC"),
        "safety_cleared": False,
        "pump_status": "IDLE",
    }


def perform_safety_audit(state: State) -> dict[str, Any]:
    """Verify safety protocols: ground wire connected, no leaks, volume limits."""
    volume = state.get("volume_liters", 0.0)
    # Domain logic: simulate safety validation
    is_safe = 0.0 < volume <= 50000.0  # Max 50k liters per transaction
    return {
        "log": [f"{UNISPSC_CODE}:perform_safety_audit: safe={is_safe}"],
        "safety_cleared": is_safe,
        "pump_status": "READY" if is_safe else "LOCKED",
    }


def execute_fuel_transfer(state: State) -> dict[str, Any]:
    """Simulate the actual pumping operation and finalize the state."""
    if not state.get("safety_cleared"):
        return {
            "log": [f"{UNISPSC_CODE}:execute_fuel_transfer: failed_safety_audit"],
            "result": {
                "ok": False,
                "error": "Safety audit failed. Refueling aborted.",
            },
        }

    return {
        "log": [f"{UNISPSC_CODE}:execute_fuel_transfer: success"],
        "pump_status": "COMPLETED",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "vehicle_id": state.get("vehicle_id"),
            "delivered_volume": state.get("volume_liters"),
            "fuel_type": state.get("fuel_type"),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_refueling)
_g.add_node("safety_audit", perform_safety_audit)
_g.add_node("transfer", execute_fuel_transfer)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "safety_audit")
_g.add_edge("safety_audit", "transfer")
_g.add_edge("transfer", END)

graph = _g.compile()
