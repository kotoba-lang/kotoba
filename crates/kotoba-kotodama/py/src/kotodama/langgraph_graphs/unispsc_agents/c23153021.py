# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153021 — Controller.
Bespoke logic for industrial control systems within manufacturing environments.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153021"
UNISPSC_TITLE = "Controller"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153021"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for industrial control
    setpoint: float
    current_reading: float
    control_output: float
    is_operational: bool
    error_delta: float


def configure_controller(state: State) -> dict[str, Any]:
    """Initializes the controller parameters from input signal."""
    inp = state.get("input") or {}
    sp = float(inp.get("setpoint", 0.0))
    return {
        "log": [f"{UNISPSC_CODE}:configure_controller(setpoint={sp})"],
        "setpoint": sp,
        "is_operational": True,
    }


def monitor_system(state: State) -> dict[str, Any]:
    """Simulates reading the current sensor value and calculating deviation."""
    inp = state.get("input") or {}
    current = float(inp.get("sensor_reading", 0.0))
    sp = state.get("setpoint", 0.0)
    delta = sp - current
    return {
        "log": [f"{UNISPSC_CODE}:monitor_system(current={current}, delta={delta})"],
        "current_reading": current,
        "error_delta": delta,
    }


def regulate_output(state: State) -> dict[str, Any]:
    """Determines the required control output based on error delta."""
    delta = state.get("error_delta", 0.0)
    # Simple proportional control logic simulation
    gain = 0.5
    signal = delta * gain

    return {
        "log": [f"{UNISPSC_CODE}:regulate_output(signal={signal})"],
        "control_output": signal,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "control_signal": signal,
            "stable": abs(delta) < 0.1,
            "status": "active" if state.get("is_operational") else "idle",
        },
    }


_g = StateGraph(State)

_g.add_node("configure", configure_controller)
_g.add_node("monitor", monitor_system)
_g.add_node("regulate", regulate_output)

_g.add_edge(START, "configure")
_g.add_edge("configure", "monitor")
_g.add_edge("monitor", "regulate")
_g.add_edge("regulate", END)

graph = _g.compile()
