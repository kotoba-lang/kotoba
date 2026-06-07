# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25171503 — Locomotive Wiper (segment 25).

Bespoke graph logic for locomotive wiper systems, managing component
inspection, motor speed calibration, and telemetry reporting.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25171503"
UNISPSC_TITLE = "Locomotive Wiper"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25171503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state fields
    blade_wear_level: float
    motor_operating_voltage: float
    target_speed_rpm: int
    environmental_load: str


def diagnose_components(state: State) -> dict[str, Any]:
    """Evaluates the physical integrity of the wiper blade and motor."""
    inp = state.get("input") or {}
    wear = inp.get("wear_sensor", 0.1)
    voltage = inp.get("line_voltage", 74.0)  # Typical locomotive DC voltage

    return {
        "log": [f"{UNISPSC_CODE}:diagnose_components"],
        "blade_wear_level": wear,
        "motor_operating_voltage": voltage,
    }


def calibrate_speed(state: State) -> dict[str, Any]:
    """Determines optimal wiper frequency based on environmental load."""
    inp = state.get("input") or {}
    condition = inp.get("precipitation", "clear")

    # Logic for locomotive wiper control
    speed_map = {
        "clear": 0,
        "mist": 20,
        "rain": 45,
        "heavy_rain": 90,
        "snow": 35
    }
    speed = speed_map.get(condition, 45)

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_speed"],
        "target_speed_rpm": speed,
        "environmental_load": condition,
    }


def generate_status_report(state: State) -> dict[str, Any]:
    """Compiles operational telemetry for the locomotive control unit."""
    is_nominal = state.get("blade_wear_level", 0) < 0.8 and state.get("motor_operating_voltage", 0) > 60

    return {
        "log": [f"{UNISPSC_CODE}:generate_status_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "OPERATIONAL" if is_nominal else "MAINTENANCE_REQUIRED",
            "telemetry": {
                "rpm": state.get("target_speed_rpm"),
                "wear": state.get("blade_wear_level"),
                "voltage": state.get("motor_operating_voltage"),
                "mode": state.get("environmental_load")
            },
            "ok": is_nominal,
        },
    }


_g = StateGraph(State)
_g.add_node("diagnose", diagnose_components)
_g.add_node("calibrate", calibrate_speed)
_g.add_node("report", generate_status_report)

_g.add_edge(START, "diagnose")
_g.add_edge("diagnose", "calibrate")
_g.add_edge("calibrate", "report")
_g.add_edge("report", END)

graph = _g.compile()
