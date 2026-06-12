# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23151806 — Laser Proc (segment 23).

Bespoke LangGraph implementation for Laser Processing automation. This agent
handles beam calibration, material verification, and process execution
within the manufacturing segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151806"
UNISPSC_TITLE = "Laser Proc"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151806"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Laser Proc domain fields
    laser_power_watts: float
    pulse_frequency_hz: int
    material_type: str
    calibration_verified: bool
    shutter_safety_active: bool


def configure_parameters(state: State) -> dict[str, Any]:
    """Initializes laser parameters based on input specifications."""
    inp = state.get("input") or {}
    material = inp.get("material", "aluminum")
    power = float(inp.get("requested_power", 500.0))

    return {
        "log": [f"{UNISPSC_CODE}:configure_parameters"],
        "material_type": material,
        "laser_power_watts": power,
        "shutter_safety_active": True,
    }


def verify_calibration(state: State) -> dict[str, Any]:
    """Ensures the laser beam is calibrated for the specified material."""
    material = state.get("material_type", "unknown")
    power = state.get("laser_power_watts", 0.0)

    # Logic: calibration is successful if power is within safe limits for material
    is_safe = 0 < power <= 2000.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_calibration (material={material})"],
        "calibration_verified": is_safe,
        "pulse_frequency_hz": 5000 if material == "steel" else 3000,
    }


def execute_laser_proc(state: State) -> dict[str, Any]:
    """Finalizes the laser process and generates the production report."""
    calibrated = state.get("calibration_verified", False)
    power = state.get("laser_power_watts", 0.0)

    success = calibrated and power > 0

    return {
        "log": [f"{UNISPSC_CODE}:execute_laser_proc (success={success})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "completed" if success else "failed",
            "parameters": {
                "power": power,
                "frequency": state.get("pulse_frequency_hz"),
                "material": state.get("material_type")
            },
            "did": UNISPSC_DID,
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("configure", configure_parameters)
_g.add_node("calibrate", verify_calibration)
_g.add_node("execute", execute_laser_proc)

_g.add_edge(START, "configure")
_g.add_edge("configure", "calibrate")
_g.add_edge("calibrate", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
