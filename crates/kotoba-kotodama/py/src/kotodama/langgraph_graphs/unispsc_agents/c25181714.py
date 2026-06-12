# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25181714 — Trailer (segment 25).

Bespoke graph logic for handling trailer lifecycle management, including
safety inspections, payload capacity validation, and dispatch manifest generation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25181714"
UNISPSC_TITLE = "Trailer"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25181714"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Trailer
    trailer_vin: str
    payload_capacity_kg: float
    current_load_kg: float
    safety_certified: bool
    maintenance_status: str


def inspect_trailer(state: State) -> dict[str, Any]:
    """Node: Validate trailer safety and basic specifications."""
    inp = state.get("input") or {}
    vin = inp.get("vin", "TRL-UNKNOWN")
    capacity = float(inp.get("capacity_kg", 5000.0))
    is_ready = inp.get("safety_pass", True)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_trailer -> VIN:{vin} | Certified:{is_ready}"],
        "trailer_vin": vin,
        "payload_capacity_kg": capacity,
        "safety_certified": is_ready,
        "maintenance_status": "inspected",
    }


def calculate_load(state: State) -> dict[str, Any]:
    """Node: Calculate current load and remaining capacity."""
    inp = state.get("input") or {}
    requested_load = float(inp.get("load_kg", 0.0))
    capacity = state.get("payload_capacity_kg", 0.0)

    if not state.get("safety_certified", False):
        return {
            "log": [f"{UNISPSC_CODE}:calculate_load -> FAILED (No Safety Certification)"],
            "current_load_kg": 0.0,
            "maintenance_status": "quarantine",
        }

    actual_load = min(requested_load, capacity)
    status = "ready_for_dispatch" if actual_load <= capacity else "overloaded"

    return {
        "log": [f"{UNISPSC_CODE}:calculate_load -> Load:{actual_load}kg | Status:{status}"],
        "current_load_kg": actual_load,
        "maintenance_status": status,
    }


def dispatch_trailer(state: State) -> dict[str, Any]:
    """Node: Finalize manifest and emit result."""
    ok = (
        state.get("safety_certified", False)
        and state.get("maintenance_status") == "ready_for_dispatch"
    )

    return {
        "log": [f"{UNISPSC_CODE}:dispatch_trailer -> Result OK:{ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "vin": state.get("trailer_vin"),
            "load_manifest": {
                "weight": state.get("current_load_kg"),
                "capacity": state.get("payload_capacity_kg"),
                "unit": "kg",
            },
            "ok": ok,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_trailer)
_g.add_node("calculate", calculate_load)
_g.add_node("dispatch", dispatch_trailer)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calculate")
_g.add_edge("calculate", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
