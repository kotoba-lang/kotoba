# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101511"
UNISPSC_TITLE = "Cart"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101511"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    load_capacity_kg: float
    current_load_kg: float
    maintenance_status: str
    location: str
    is_operational: bool


def inspect_chassis(state: State) -> dict[str, Any]:
    """Check cart integrity and maintenance logs."""
    inp = state.get("input") or {}
    status = inp.get("initial_status", "serviceable")
    is_ok = status == "serviceable"
    return {
        "log": [f"{UNISPSC_CODE}:inspect_chassis:{status}"],
        "maintenance_status": status,
        "is_operational": is_ok,
        "load_capacity_kg": 450.0,
    }


def allocate_payload(state: State) -> dict[str, Any]:
    """Calculate and assign weight to the cart chassis."""
    if not state.get("is_operational"):
        return {"log": [f"{UNISPSC_CODE}:allocate_payload:skipped_maintenance_fail"]}

    inp = state.get("input") or {}
    requested_load = float(inp.get("payload_weight", 0.0))
    capacity = state.get("load_capacity_kg", 0.0)

    # Simulate loading logic
    actual_load = min(requested_load, capacity)
    overloaded = requested_load > capacity

    msg = f"load:{actual_load}kg"
    if overloaded:
        msg += ":capped_at_max_capacity"

    return {
        "log": [f"{UNISPSC_CODE}:{msg}"],
        "current_load_kg": actual_load,
        "location": inp.get("destination", "distribution_bay_1")
    }


def finalize_dispatch(state: State) -> dict[str, Any]:
    """Seal the operation and generate the manifest."""
    is_ready = state.get("is_operational", False)
    load = state.get("current_load_kg", 0.0)
    loc = state.get("location", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_dispatch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "payload_kg": load,
            "destination": loc,
            "status": "dispatched" if is_ready else "quarantined",
            "ok": is_ready
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_chassis)
_g.add_node("load", allocate_payload)
_g.add_node("dispatch", finalize_dispatch)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "load")
_g.add_edge("load", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
