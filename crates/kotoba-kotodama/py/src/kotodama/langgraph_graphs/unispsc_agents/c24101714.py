# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101714 — Conveyor (segment 24).

This bespoke implementation manages the operational logic for a conveyor system,
including load detection, speed regulation based on weight, and routing control.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101714"
UNISPSC_TITLE = "Conveyor"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101714"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific state for Conveyor
    load_weight_kg: float
    belt_speed_m_s: float
    target_zone: str
    safety_interlock: bool


def initialize_conveyor(state: State) -> dict[str, Any]:
    """Initializes the conveyor state from input and verifies safety interlocks."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight_kg", 0.0))
    # Simulate a safety check: interlock is false if weight is dangerously high
    is_safe = weight < 1000.0

    return {
        "log": [f"{UNISPSC_CODE}:initialize_conveyor"],
        "load_weight_kg": weight,
        "safety_interlock": is_safe,
        "belt_speed_m_s": 0.0
    }


def regulate_load(state: State) -> dict[str, Any]:
    """Adjusts belt speed based on the load weight and safety status."""
    if not state.get("safety_interlock", False):
        return {
            "log": [f"{UNISPSC_CODE}:regulate_load:emergency_stop"],
            "belt_speed_m_s": 0.0,
            "target_zone": "quarantine"
        }

    weight = state.get("load_weight_kg", 0.0)
    # Heuristic: heavier loads move slower
    if weight > 500.0:
        speed = 0.5
    elif weight > 0:
        speed = 1.2
    else:
        speed = 0.0

    return {
        "log": [f"{UNISPSC_CODE}:regulate_load:active"],
        "belt_speed_m_s": speed,
        "target_zone": "sorting_bay_alpha" if weight < 200 else "sorting_bay_beta"
    }


def dispatch_unit(state: State) -> dict[str, Any]:
    """Finalizes the transport operation and emits the result."""
    zone = state.get("target_zone", "idle")
    speed = state.get("belt_speed_m_s", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:dispatch_unit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "operation_status": "complete" if speed > 0 or zone != "idle" else "standby",
            "assigned_zone": zone,
            "final_speed": speed,
            "ok": state.get("safety_interlock", False),
        },
    }


_g = StateGraph(State)

_g.add_node("initialize", initialize_conveyor)
_g.add_node("regulate", regulate_load)
_g.add_node("dispatch", dispatch_unit)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "regulate")
_g.add_edge("regulate", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
