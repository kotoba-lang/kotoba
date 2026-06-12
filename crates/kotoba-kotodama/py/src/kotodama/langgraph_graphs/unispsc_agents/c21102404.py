# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21102404 — Mower (segment 21).

Bespoke implementation for lawn maintenance machinery automation.
Provides nodes for safety inspection, height configuration, and operational dispatch.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21102404"
UNISPSC_TITLE = "Mower"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21102404"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields for "Mower"
    blade_sharpness_index: float
    safety_sensor_active: bool
    cutting_height_setting_mm: int
    fuel_level_percent: float


def initialize_inspection(state: State) -> dict[str, Any]:
    """Verify mower safety systems and component status before operation."""
    inp = state.get("input") or {}
    # Simulate hardware check logic
    initial_sharpness = float(inp.get("initial_sharpness", 0.85))
    safety_check = inp.get("safety_check", True)
    fuel = float(inp.get("fuel", 100.0))

    return {
        "log": [f"{UNISPSC_CODE}:initialize_inspection"],
        "blade_sharpness_index": initial_sharpness,
        "safety_sensor_active": safety_check,
        "fuel_level_percent": fuel,
    }


def set_cutting_parameters(state: State) -> dict[str, Any]:
    """Configure the mower's deck height based on input constraints."""
    inp = state.get("input") or {}
    requested_height = int(inp.get("height_mm", 40))

    # Enforce mechanical limits for a standard industrial mower (25mm to 100mm)
    clamped_height = max(25, min(100, requested_height))

    return {
        "log": [f"{UNISPSC_CODE}:set_cutting_parameters"],
        "cutting_height_setting_mm": clamped_height,
    }


def perform_dispatch(state: State) -> dict[str, Any]:
    """Validate all states and finalize the mower deployment result."""
    is_safe = state.get("safety_sensor_active", False)
    is_fueled = state.get("fuel_level_percent", 0.0) > 5.0
    is_sharp = state.get("blade_sharpness_index", 0.0) > 0.4

    operational = is_safe and is_fueled and is_sharp

    return {
        "log": [f"{UNISPSC_CODE}:perform_dispatch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operational_status": "dispatched" if operational else "maintenance_required",
            "telemetry": {
                "height_mm": state.get("cutting_height_setting_mm"),
                "fuel_remaining": state.get("fuel_level_percent"),
                "blade_health": "ok" if is_sharp else "dull"
            },
            "ok": operational,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", initialize_inspection)
_g.add_node("configure", set_cutting_parameters)
_g.add_node("dispatch", perform_dispatch)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "configure")
_g.add_edge("configure", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
