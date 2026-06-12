# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101700 — Irrigation (segment 21).

Bespoke graph logic for managing irrigation cycles, including sensor validation,
hydraulic calculation, and cycle execution.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101700"
UNISPSC_TITLE = "Irrigation"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101700"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    soil_moisture_index: float
    valve_open_duration: int
    water_pressure_psi: float
    zone_identifier: str


def validate_sensors(state: State) -> dict[str, Any]:
    """Validate incoming moisture and pressure sensor data."""
    inp = state.get("input") or {}
    moisture = inp.get("soil_moisture", 45.0)
    pressure = inp.get("pressure", 60.0)
    zone = inp.get("zone", "A1")

    return {
        "log": [f"{UNISPSC_CODE}:validate_sensors"],
        "soil_moisture_index": float(moisture),
        "water_pressure_psi": float(pressure),
        "zone_identifier": str(zone),
    }


def calculate_irrigation_load(state: State) -> dict[str, Any]:
    """Determine the necessary duration based on soil moisture levels."""
    moisture = state.get("soil_moisture_index", 100.0)

    # Calculate duration: less moisture requires longer valve opening
    if moisture < 20:
        duration = 45
    elif moisture < 50:
        duration = 20
    else:
        duration = 0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_irrigation_load"],
        "valve_open_duration": duration,
    }


def execute_irrigation_cycle(state: State) -> dict[str, Any]:
    """Log the execution of the cycle and prepare final telemetry."""
    duration = state.get("valve_open_duration", 0)
    zone = state.get("zone_identifier", "unknown")
    pressure = state.get("water_pressure_psi", 0.0)

    status = "completed" if duration > 0 else "skipped_sufficient_moisture"

    return {
        "log": [f"{UNISPSC_CODE}:execute_irrigation_cycle"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "execution": {
                "zone": zone,
                "duration_minutes": duration,
                "operating_pressure_psi": pressure,
                "status": status,
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_sensors", validate_sensors)
_g.add_node("calculate_irrigation_load", calculate_irrigation_load)
_g.add_node("execute_irrigation_cycle", execute_irrigation_cycle)

_g.add_edge(START, "validate_sensors")
_g.add_edge("validate_sensors", "calculate_irrigation_load")
_g.add_edge("calculate_irrigation_load", "execute_irrigation_cycle")
_g.add_edge("execute_irrigation_cycle", END)

graph = _g.compile()
