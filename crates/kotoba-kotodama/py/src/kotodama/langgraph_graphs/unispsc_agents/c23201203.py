# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23201203 — Engine (segment 23).

Bespoke graph logic for Engine telemetry and performance monitoring.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23201203"
UNISPSC_TITLE = "Engine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23201203"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Engine
    rpm: int
    operating_temp: float
    fuel_flow_rate: float
    is_stable: bool


def initialize_system(state: State) -> dict[str, Any]:
    """Initializes engine parameters from input or defaults."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:initialize_system"],
        "rpm": inp.get("target_rpm", 0),
        "operating_temp": 25.0,
        "fuel_flow_rate": 0.0,
        "is_stable": False,
    }


def calculate_dynamics(state: State) -> dict[str, Any]:
    """Simulates engine thermodynamic and mechanical dynamics."""
    rpm = state.get("rpm", 0)
    # Simple simulation: temperature increases with rpm
    new_temp = 25.0 + (rpm * 0.05)
    flow = rpm * 0.001
    # Define stable operating range
    stable = 500 < rpm < 8000

    return {
        "log": [f"{UNISPSC_CODE}:calculate_dynamics"],
        "operating_temp": new_temp,
        "fuel_flow_rate": flow,
        "is_stable": stable,
    }


def generate_telemetry(state: State) -> dict[str, Any]:
    """Prepares the final telemetry result for the engine state."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "rpm": state.get("rpm"),
                "temp_c": state.get("operating_temp"),
                "fuel_flow": state.get("fuel_flow_rate"),
                "status": "nominal" if state.get("is_stable") else "alert",
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("initialize_system", initialize_system)
_g.add_node("calculate_dynamics", calculate_dynamics)
_g.add_node("generate_telemetry", generate_telemetry)

_g.add_edge(START, "initialize_system")
_g.add_edge("initialize_system", "calculate_dynamics")
_g.add_edge("calculate_dynamics", "generate_telemetry")
_g.add_edge("generate_telemetry", END)

graph = _g.compile()
