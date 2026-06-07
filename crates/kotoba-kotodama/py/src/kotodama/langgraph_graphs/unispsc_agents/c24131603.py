# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24131603 — Freezer (segment 24).

This agent manages the state and telemetry logic for industrial freezer units,
handling temperature monitoring, door security validation, and cooling cycle
calculations for the Etz Hayyim actor network.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24131603"
UNISPSC_TITLE = "Freezer"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24131603"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Freezer
    current_temp_celsius: float
    target_temp_celsius: float
    door_sealed: bool
    compressor_active: bool
    power_efficiency_rating: float


def monitor_thermal_state(state: State) -> dict[str, Any]:
    """Ingests sensor data to establish the current thermal baseline."""
    inp = state.get("input") or {}
    cur_temp = float(inp.get("current_temp", -18.5))
    target_temp = float(inp.get("target_temp", -20.0))
    door_status = bool(inp.get("door_sealed", True))

    return {
        "log": [f"{UNISPSC_CODE}:monitor_thermal_state(temp={cur_temp}, sealed={door_status})"],
        "current_temp_celsius": cur_temp,
        "target_temp_celsius": target_temp,
        "door_sealed": door_status,
    }


def regulate_cooling_cycle(state: State) -> dict[str, Any]:
    """Determines compressor engagement based on thermal variance and door safety."""
    cur = state.get("current_temp_celsius", 0.0)
    target = state.get("target_temp_celsius", 0.0)
    sealed = state.get("door_sealed", False)

    # Engage compressor if above target and door is secure to prevent energy waste
    active = (cur > target) and sealed
    efficiency = 0.95 if sealed else 0.40

    return {
        "log": [f"{UNISPSC_CODE}:regulate_cooling_cycle(active={active}, efficiency={efficiency})"],
        "compressor_active": active,
        "power_efficiency_rating": efficiency,
    }


def emit_telemetry_report(state: State) -> dict[str, Any]:
    """Packages the operational metrics into a standardized actor response."""
    temp = state.get("current_temp_celsius", 0.0)
    is_safe = temp < -10.0 and state.get("door_sealed", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_telemetry_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "temperature": temp,
                "compressor": state.get("compressor_active"),
                "efficiency": state.get("power_efficiency_rating"),
            },
            "ok": is_safe,
        },
    }


_g = StateGraph(State)

_g.add_node("monitor", monitor_thermal_state)
_g.add_node("regulate", regulate_cooling_cycle)
_g.add_node("emit", emit_telemetry_report)

_g.add_edge(START, "monitor")
_g.add_edge("monitor", "regulate")
_g.add_edge("regulate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
