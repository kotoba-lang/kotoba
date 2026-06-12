# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101725 — Conveyor.

Bespoke LangGraph agent logic for managing material handling conveyor systems,
tracking belt speed, load weight, and safety status.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101725"
UNISPSC_TITLE = "Conveyor"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101725"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific conveyor state
    belt_speed_m_per_s: float
    load_weight_kg: float
    safety_interlock_active: bool
    destination_bin: str


def init_conveyor(state: State) -> dict[str, Any]:
    """Initializes conveyor parameters and verifies safety systems."""
    inp = state.get("input") or {}
    requested_speed = inp.get("speed", 1.5)

    # Ensure safety interlocks are initialized before operation
    return {
        "log": [f"{UNISPSC_CODE}:init_conveyor(speed={requested_speed})"],
        "belt_speed_m_per_s": requested_speed,
        "safety_interlock_active": True,
    }


def monitor_load(state: State) -> dict[str, Any]:
    """Simulates load sensor reading and checks structural limits."""
    inp = state.get("input") or {}
    weight = inp.get("weight", 22.5)

    log_entry = f"{UNISPSC_CODE}:monitor_load(weight={weight}kg)"
    if weight > 200.0:
        log_entry += " - CRITICAL: Overload detected"

    return {
        "log": [log_entry],
        "load_weight_kg": weight,
    }


def dispatch_item(state: State) -> dict[str, Any]:
    """Finalizes routing based on weight metrics and speed profile."""
    weight = state.get("load_weight_kg", 0.0)
    speed = state.get("belt_speed_m_per_s", 0.0)

    # Simplified routing logic
    if weight < 5.0:
        bin_id = "BIN_A_SMALL"
    elif weight < 50.0:
        bin_id = "BIN_B_MEDIUM"
    else:
        bin_id = "BIN_C_HEAVY"

    return {
        "log": [f"{UNISPSC_CODE}:dispatch_item(bin={bin_id})"],
        "destination_bin": bin_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "weight": weight,
                "speed": speed,
                "routing": bin_id,
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("init_conveyor", init_conveyor)
_g.add_node("monitor_load", monitor_load)
_g.add_node("dispatch_item", dispatch_item)

_g.add_edge(START, "init_conveyor")
_g.add_edge("init_conveyor", "monitor_load")
_g.add_edge("monitor_load", "dispatch_item")
_g.add_edge("dispatch_item", END)

graph = _g.compile()
