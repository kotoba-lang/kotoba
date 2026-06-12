# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24131503 — Refrigerator (segment 24).

Bespoke LangGraph implementation for refrigerator monitoring and thermal regulation.
This agent processes telemetry to evaluate cooling efficiency and hardware status.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24131503"
UNISPSC_TITLE = "Refrigerator"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24131503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Refrigerator domain state
    current_temp: float
    target_temp: float
    compressor_load: float
    door_closed: bool
    alarm_active: bool


def ingest_telemetry(state: State) -> dict[str, Any]:
    """Validates and ingests refrigerator sensor data."""
    inp = state.get("input") or {}
    temp = float(inp.get("temperature_c", 4.0))
    setpoint = float(inp.get("setpoint_c", 3.0))
    door_state = bool(inp.get("door_sensor_closed", True))

    return {
        "log": [f"{UNISPSC_CODE}:ingest_telemetry"],
        "current_temp": temp,
        "target_temp": setpoint,
        "door_closed": door_state
    }


def regulate_thermal_load(state: State) -> dict[str, Any]:
    """Determines compressor activity based on temperature delta and door status."""
    temp = state.get("current_temp", 4.0)
    target = state.get("target_temp", 3.0)
    door_ok = state.get("door_closed", True)

    # Calculate load: if door is open or temp is high, increase load
    load = 0.0
    if temp > target:
        load = min(1.0, (temp - target) / 5.0)

    alarm = not door_ok and temp > 8.0

    return {
        "log": [f"{UNISPSC_CODE}:regulate_thermal_load"],
        "compressor_load": load,
        "alarm_active": alarm
    }


def generate_status_report(state: State) -> dict[str, Any]:
    """Finalizes the operational status report for the cooling unit."""
    is_nominal = state.get("current_temp", 4.0) < 10.0 and not state.get("alarm_active")

    return {
        "log": [f"{UNISPSC_CODE}:generate_status_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "operational": is_nominal,
            "telemetry": {
                "temp": state.get("current_temp"),
                "load": state.get("compressor_load"),
                "alarm": state.get("alarm_active")
            }
        }
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_telemetry)
_g.add_node("regulate", regulate_thermal_load)
_g.add_node("report", generate_status_report)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "regulate")
_g.add_edge("regulate", "report")
_g.add_edge("report", END)

graph = _g.compile()
