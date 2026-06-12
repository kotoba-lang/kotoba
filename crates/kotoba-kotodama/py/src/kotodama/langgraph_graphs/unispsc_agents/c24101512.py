# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101512 — Power buggies.

This bespoke graph manages the operational lifecycle of a power buggy,
including battery diagnostics, payload validation, and dispatch readiness.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101512"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101512"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Power buggies
    battery_level: float
    payload_weight_lbs: float
    is_operational: bool
    safety_brake_engaged: bool


def inspect_vehicle(state: State) -> dict[str, Any]:
    """Node: Inspect the mechanical and electrical status of the power buggy."""
    inp = state.get("input") or {}
    battery = float(inp.get("battery", 100.0))
    brake = bool(inp.get("brake_engaged", False))

    # Motor is operational only if battery > 15% and safety brake is disengaged
    operational = battery > 15.0 and not brake

    return {
        "log": [f"{UNISPSC_CODE}:inspect_vehicle"],
        "battery_level": battery,
        "safety_brake_engaged": brake,
        "is_operational": operational
    }


def validate_load(state: State) -> dict[str, Any]:
    """Node: Validate if the hauling payload is within the buggy's safety limits."""
    inp = state.get("input") or {}
    weight = float(inp.get("payload", 0.0))
    max_capacity = 2500.0  # Standard industrial power buggy limit in lbs

    operational = state.get("is_operational", False)
    if weight > max_capacity:
        operational = False

    return {
        "log": [f"{UNISPSC_CODE}:validate_load"],
        "payload_weight_lbs": weight,
        "is_operational": operational
    }


def finalize_dispatch(state: State) -> dict[str, Any]:
    """Node: Consolidate telemetry and emit the final operation status."""
    is_ok = state.get("is_operational", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_dispatch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": is_ok,
            "status": "DISPATCH_READY" if is_ok else "MAINTENANCE_REQUIRED",
            "telemetry": {
                "charge": state.get("battery_level"),
                "load": state.get("payload_weight_lbs"),
                "safety_lock": state.get("safety_brake_engaged")
            }
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_vehicle", inspect_vehicle)
_g.add_node("validate_load", validate_load)
_g.add_node("finalize_dispatch", finalize_dispatch)

_g.add_edge(START, "inspect_vehicle")
_g.add_edge("inspect_vehicle", "validate_load")
_g.add_edge("validate_load", "finalize_dispatch")
_g.add_edge("finalize_dispatch", END)

graph = _g.compile()
