# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101626 — Escalator (segment 24).

Bespoke graph logic for monitoring and controlling escalator operations,
ensuring safety protocols and load management are maintained.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101626"
UNISPSC_TITLE = "Escalator"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101626"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific Escalator state fields
    safety_check_passed: bool
    operating_status: str
    load_weight_kg: float
    emergency_stop_active: bool
    maintenance_required: bool


def inspect(state: State) -> dict[str, Any]:
    """Node: Perform mechanical and safety sensor inspection."""
    inp = state.get("input") or {}
    emergency_trigger = inp.get("emergency_trigger", False)
    load = float(inp.get("load_weight", 0.0))

    # Safety logic: check for emergency signals and weight limits
    # Max load for this specific escalator model is 4500kg
    safety_ok = not emergency_trigger and load < 4500.0

    return {
        "log": [f"{UNISPSC_CODE}:inspect -> safety_ok: {safety_ok}"],
        "safety_check_passed": safety_ok,
        "emergency_stop_active": emergency_trigger,
        "load_weight_kg": load
    }


def control_logic(state: State) -> dict[str, Any]:
    """Node: Determine motor power and directional state based on sensors."""
    safety_ok = state.get("safety_check_passed", False)
    e_stop = state.get("emergency_stop_active", False)

    if not safety_ok:
        status = "STOPPED_ERROR"
        maint = True
    elif e_stop:
        status = "EMERGENCY_HALT"
        maint = False
    else:
        status = "RUNNING_NOMINAL"
        maint = False

    return {
        "log": [f"{UNISPSC_CODE}:control_logic -> {status}"],
        "operating_status": status,
        "maintenance_required": maint
    }


def notify(state: State) -> dict[str, Any]:
    """Node: Emit final operational metrics and status code."""
    status = state.get("operating_status", "UNKNOWN")
    maint = state.get("maintenance_required", False)

    return {
        "log": [f"{UNISPSC_CODE}:notify"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "operational_status": status,
            "requires_service": maint,
            "load_at_execution": state.get("load_weight_kg", 0.0),
            "ok": status == "RUNNING_NOMINAL"
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect)
_g.add_node("control_logic", control_logic)
_g.add_node("notify", notify)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "control_logic")
_g.add_edge("control_logic", "notify")
_g.add_edge("notify", END)

graph = _g.compile()
