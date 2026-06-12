# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23241601 — Robot (segment 23).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23241601"
UNISPSC_TITLE = "Robot"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23241601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    battery_level: float
    calibration_offset: float
    active_subsystems: list[str]
    safety_interlock_engaged: bool


def diagnose_hardware(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    battery = inp.get("battery", 100.0)
    return {
        "log": [f"{UNISPSC_CODE}:diagnose_hardware"],
        "battery_level": battery,
        "active_subsystems": ["vision", "locomotion", "haptics"],
        "safety_interlock_engaged": battery < 10.0,
    }


def calibrate_actuators(state: State) -> dict[str, Any]:
    is_safe = not state.get("safety_interlock_engaged", False)
    offset = 0.0042 if is_safe else 0.0
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_actuators"],
        "calibration_offset": offset,
    }


def generate_telemetry(state: State) -> dict[str, Any]:
    battery = state.get("battery_level", 0.0)
    subsystems = state.get("active_subsystems") or []
    offset = state.get("calibration_offset", 0.0)
    interlock = state.get("safety_interlock_engaged", False)

    return {
        "log": [f"{UNISPSC_CODE}:generate_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "ready" if battery > 15.0 and not interlock else "maintenance_required",
            "telemetry": {
                "subsystems_online": len(subsystems),
                "calibration_offset": offset,
                "battery_percentage": battery,
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("diagnose_hardware", diagnose_hardware)
_g.add_node("calibrate_actuators", calibrate_actuators)
_g.add_node("generate_telemetry", generate_telemetry)

_g.add_edge(START, "diagnose_hardware")
_g.add_edge("diagnose_hardware", "calibrate_actuators")
_g.add_edge("calibrate_actuators", "generate_telemetry")
_g.add_edge("generate_telemetry", END)

graph = _g.compile()
