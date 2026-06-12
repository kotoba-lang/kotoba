# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101750 — Throttle (segment 26).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101750"
UNISPSC_TITLE = "Throttle"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101750"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    throttle_position: float
    flow_pressure: float
    actuator_status: str
    diagnostic_code: str


def check_actuator(state: State) -> dict[str, Any]:
    """Verify the physical integrity and position of the throttle actuator."""
    inp = state.get("input") or {}
    # Expect target_position between 0.0 (closed) and 1.0 (wide open)
    try:
        position = float(inp.get("target_position", 0.0))
    except (ValueError, TypeError):
        position = 0.0

    status = "nominal" if 0.0 <= position <= 1.0 else "out_of_range"
    diag = "THR-OK" if status == "nominal" else "THR-ERR-VAL"

    return {
        "log": [f"{UNISPSC_CODE}:check_actuator: status={status} pos={position}"],
        "throttle_position": max(0.0, min(1.0, position)),
        "actuator_status": status,
        "diagnostic_code": diag
    }


def calculate_flow(state: State) -> dict[str, Any]:
    """Simulate fluid/air flow regulation based on the current throttle position."""
    pos = state.get("throttle_position", 0.0)
    # Simple linear flow model: pressure (kPa) = position * max_rated_pressure
    max_rated_pressure = 850.0
    pressure = pos * max_rated_pressure

    return {
        "log": [f"{UNISPSC_CODE}:calculate_flow: effective_pressure={pressure}kPa"],
        "flow_pressure": pressure
    }


def dispatch_telemetry(state: State) -> dict[str, Any]:
    """Emit the final synthesized state of the throttle assembly."""
    return {
        "log": [f"{UNISPSC_CODE}:dispatch_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "position_pct": round(state.get("throttle_position", 0.0) * 100, 2),
                "pressure_kpa": round(state.get("flow_pressure", 0.0), 2),
                "actuator_state": state.get("actuator_status"),
                "diag_code": state.get("diagnostic_code")
            },
            "execution_success": True
        }
    }


_g = StateGraph(State)

_g.add_node("check_actuator", check_actuator)
_g.add_node("calculate_flow", calculate_flow)
_g.add_node("dispatch_telemetry", dispatch_telemetry)

_g.add_edge(START, "check_actuator")
_g.add_edge("check_actuator", "calculate_flow")
_g.add_edge("calculate_flow", "dispatch_telemetry")
_g.add_edge("dispatch_telemetry", END)

graph = _g.compile()
