# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172704 — Climate System (segment 25).

Bespoke LangGraph implementation for managing climate control systems,
regulating temperature, and monitoring system diagnostics.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172704"
UNISPSC_TITLE = "Climate System"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172704"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Climate System management
    ambient_temp: float
    setpoint_temp: float
    fan_speed: int
    compressor_active: bool
    filter_status: str


def monitor_environment(state: State) -> dict[str, Any]:
    """Analyzes current environmental data against desired setpoints."""
    inp = state.get("input") or {}
    ambient = inp.get("ambient_temp", 22.5)
    setpoint = inp.get("setpoint_temp", 20.0)

    return {
        "log": [f"{UNISPSC_CODE}:monitor_environment(ambient={ambient}, setpoint={setpoint})"],
        "ambient_temp": ambient,
        "setpoint_temp": setpoint,
        "filter_status": inp.get("filter_status", "nominal"),
    }


def regulate_climate(state: State) -> dict[str, Any]:
    """Determines necessary system adjustments to reach the thermal setpoint."""
    ambient = state.get("ambient_temp", 0.0)
    setpoint = state.get("setpoint_temp", 0.0)

    # Simple HVAC control logic
    diff = ambient - setpoint
    compressor = diff > 0.5  # Activate cooling if too warm
    speed = min(100, int(abs(diff) * 20)) if abs(diff) > 0.2 else 0

    return {
        "log": [f"{UNISPSC_CODE}:regulate_climate(diff={diff:.2f}, compressor={compressor})"],
        "compressor_active": compressor,
        "fan_speed": speed,
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Generates the final system status report and operational telemetry."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "compressor_active": state.get("compressor_active", False),
                "fan_percent": state.get("fan_speed", 0),
                "ambient": state.get("ambient_temp"),
                "setpoint": state.get("setpoint_temp"),
                "filter": state.get("filter_status"),
            },
            "status": "ready",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("monitor", monitor_environment)
_g.add_node("regulate", regulate_climate)
_g.add_node("finalize", finalize_telemetry)

_g.add_edge(START, "monitor")
_g.add_edge("monitor", "regulate")
_g.add_edge("regulate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
