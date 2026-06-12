# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23231501 — Actuator (segment 23).

Bespoke graph logic for actuator control simulations. This agent handles
calibration, motion execution, and telemetry reporting for industrial
actuators within the Etz Hayyim actor network.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23231501"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23231501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Actuator-specific state fields
    target_displacement: float
    current_displacement: float
    load_factor: float
    status_flags: list[str]
    system_pressure: float


def initialize_hardware(state: State) -> dict[str, Any]:
    """Initializes sensor readings and sets up default pressure levels."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 45.0))
    return {
        "log": [f"{UNISPSC_CODE}:initialize_hardware"],
        "system_pressure": pressure,
        "status_flags": ["powered_on", "online"],
        "current_displacement": state.get("current_displacement", 0.0),
    }


def process_displacement(state: State) -> dict[str, Any]:
    """Calculates movement logic based on target input and load factor."""
    inp = state.get("input") or {}
    target = float(inp.get("target", 0.0))
    load = float(inp.get("load", 1.0))

    # Logic: if pressure is sufficient, move to target
    current_flags = state.get("status_flags") or []
    if state.get("system_pressure", 0.0) >= 30.0:
        new_pos = target
        flags = current_flags + ["moving"]
    else:
        new_pos = state.get("current_displacement", 0.0)
        flags = current_flags + ["low_pressure_warning"]

    return {
        "log": [f"{UNISPSC_CODE}:process_displacement"],
        "target_displacement": target,
        "current_displacement": new_pos,
        "load_factor": load,
        "status_flags": flags,
    }


def generate_telemetry(state: State) -> dict[str, Any]:
    """Aggregates final state into a standardized Unispsc response."""
    flags = state.get("status_flags") or []
    success = "low_pressure_warning" not in flags

    return {
        "log": [f"{UNISPSC_CODE}:generate_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "telemetry": {
                "displacement": state.get("current_displacement"),
                "pressure": state.get("system_pressure"),
                "load": state.get("load_factor"),
            },
            "flags": flags,
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_hardware)
_g.add_node("process", process_displacement)
_g.add_node("telemetry", generate_telemetry)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "process")
_g.add_edge("process", "telemetry")
_g.add_edge("telemetry", END)

graph = _g.compile()
