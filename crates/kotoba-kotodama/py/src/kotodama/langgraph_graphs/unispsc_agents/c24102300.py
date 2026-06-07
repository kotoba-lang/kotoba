# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Bespose agent for UNISPSC 24102300 — A G V (Automated Guided Vehicles).
Focuses on autonomous material handling, pathfinding, and safety protocols.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24102300"
UNISPSC_TITLE = "A G V"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24102300"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Automated Guided Vehicles
    battery_level: float
    path_coordinates: list[tuple[int, int]]
    safety_clearance: bool
    load_weight_kg: float


def verify_telemetry(state: State) -> dict[str, Any]:
    """Check battery levels and physical safety sensors."""
    inp = state.get("input") or {}
    battery = inp.get("battery", 95.0)
    weight = inp.get("weight", 0.0)

    # Simple logic: block if battery is too low or weight exceeds safety limit
    is_safe = battery > 15.0 and weight < 2000.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_telemetry"],
        "battery_level": battery,
        "load_weight_kg": weight,
        "safety_clearance": is_safe,
    }


def compute_route(state: State) -> dict[str, Any]:
    """Calculate the navigation path for the AGV."""
    if not state.get("safety_clearance"):
        return {"log": [f"{UNISPSC_CODE}:compute_route_blocked_safety"]}

    inp = state.get("input") or {}
    dest = inp.get("destination", "warehouse_zone_A")

    # Mock pathfinding logic based on destination
    path = [(0, 0), (10, 5), (20, 10)] if "A" in dest else [(0, 0), (5, 2), (10, 10)]

    return {
        "log": [f"{UNISPSC_CODE}:compute_route_success"],
        "path_coordinates": path,
    }


def dispatch_vehicle(state: State) -> dict[str, Any]:
    """Finalize the mission and return the execution summary."""
    success = state.get("safety_clearance", False) and bool(state.get("path_coordinates"))

    return {
        "log": [f"{UNISPSC_CODE}:dispatch_vehicle"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "active_transit" if success else "immobilized",
            "battery_status": f"{state.get('battery_level', 0):.1f}%",
            "path_points": len(state.get("path_coordinates") or []),
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("verify_telemetry", verify_telemetry)
_g.add_node("compute_route", compute_route)
_g.add_node("dispatch_vehicle", dispatch_vehicle)

_g.add_edge(START, "verify_telemetry")
_g.add_edge("verify_telemetry", "compute_route")
_g.add_edge("compute_route", "dispatch_vehicle")
_g.add_edge("dispatch_vehicle", END)

graph = _g.compile()
