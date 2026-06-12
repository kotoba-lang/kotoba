# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25174000 — Cooling System (segment 25).

Bespoke graph logic for monitoring and regulating industrial cooling systems.
This agent tracks temperature sensors, coolant pressure, and fan speeds to
ensure thermal stability across the cooling infrastructure.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174000"
UNISPSC_TITLE = "Cooling System"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific cooling system fields
    temperature_celsius: float
    coolant_pressure_bar: float
    fan_speed_rpm: int
    thermal_stability_level: str


def ingest_telemetry(state: State) -> dict[str, Any]:
    """Parses incoming sensor telemetry from the cooling system hardware."""
    inp = state.get("input") or {}
    temp = float(inp.get("temp", 18.5))
    pressure = float(inp.get("pressure", 4.2))

    return {
        "log": [f"{UNISPSC_CODE}:ingest_telemetry(temp={temp}C, p={pressure}bar)"],
        "temperature_celsius": temp,
        "coolant_pressure_bar": pressure,
    }


def regulate_thermal_load(state: State) -> dict[str, Any]:
    """Adjusts mechanical components based on current thermal state."""
    temp = state.get("temperature_celsius", 0.0)

    # Calculate fan speed based on delta from baseline
    if temp > 45.0:
        fan_rpm = 4500
        stability = "UNSTABLE"
    elif temp > 30.0:
        fan_rpm = 2800
        stability = "STRESS"
    else:
        fan_rpm = 1200
        stability = "OPTIMAL"

    return {
        "log": [f"{UNISPSC_CODE}:regulate_thermal_load(fan={fan_rpm}rpm, stability={stability})"],
        "fan_speed_rpm": fan_rpm,
        "thermal_stability_level": stability,
    }


def generate_status_report(state: State) -> dict[str, Any]:
    """Finalizes the system state and prepares the actor response."""
    stability = state.get("thermal_stability_level", "UNKNOWN")
    return {
        "log": [f"{UNISPSC_CODE}:generate_status_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metrics": {
                "temp": state.get("temperature_celsius"),
                "pressure": state.get("coolant_pressure_bar"),
                "rpm": state.get("fan_speed_rpm"),
            },
            "stability": stability,
            "operational": stability != "UNSTABLE",
            "ok": True,
        },
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
