# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101513"
UNISPSC_TITLE = "Irrigation"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101513"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    soil_moisture_level: float
    target_moisture_level: float
    system_pressure_psi: float
    valve_position_percent: int
    scheduled_duration_minutes: int


def monitor_soil(state: State) -> dict[str, Any]:
    """Analyzes current soil moisture and compares against target thresholds."""
    inp = state.get("input") or {}
    current = float(inp.get("moisture", 32.5))
    target = float(inp.get("target", 45.0))
    return {
        "log": [f"{UNISPSC_CODE}:monitor_soil"],
        "soil_moisture_level": current,
        "target_moisture_level": target,
    }


def calculate_schedule(state: State) -> dict[str, Any]:
    """Determines valve intensity and duration based on moisture deficit."""
    current = state.get("soil_moisture_level", 0.0)
    target = state.get("target_moisture_level", 0.0)

    if current < target:
        deficit = target - current
        valve_pos = 100 if deficit > 10 else 50
        duration = int(deficit * 2)
    else:
        valve_pos = 0
        duration = 0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_schedule"],
        "valve_position_percent": valve_pos,
        "scheduled_duration_minutes": duration,
        "system_pressure_psi": 42.5 if valve_pos > 0 else 0.0
    }


def validate_safety(state: State) -> dict[str, Any]:
    """Verifies that irrigation parameters do not exceed hardware safety limits."""
    pressure = state.get("system_pressure_psi", 0.0)
    duration = state.get("scheduled_duration_minutes", 0)

    # Safety check: Prevent water hammer or over-saturation
    is_safe = pressure < 80.0 and duration < 120

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety"],
        "result": {
            "is_safe": is_safe,
            "valve_pos": state.get("valve_position_percent"),
            "duration": duration,
            "pressure": pressure
        }
    }


def emit_irrigation_plan(state: State) -> dict[str, Any]:
    """Constructs the final irrigation dispatch result."""
    res = state.get("result") or {}
    res.update({
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "ok": res.get("is_safe", False),
    })
    return {
        "log": [f"{UNISPSC_CODE}:emit_irrigation_plan"],
        "result": res,
    }


_g = StateGraph(State)
_g.add_node("monitor", monitor_soil)
_g.add_node("calculate", calculate_schedule)
_g.add_node("validate", validate_safety)
_g.add_node("emit", emit_irrigation_plan)

_g.add_edge(START, "monitor")
_g.add_edge("monitor", "calculate")
_g.add_edge("calculate", "validate")
_g.add_edge("validate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
