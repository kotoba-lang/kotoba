# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101605 — Irrigation (segment 21).

Bespoke graph logic for managing irrigation system state, optimizing flow,
and monitoring soil moisture sensors.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101605"
UNISPSC_TITLE = "Irrigation"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101605"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    soil_moisture_level: float
    water_source_available: bool
    target_pressure_psi: float
    system_health_status: str


def monitor_sensor(state: State) -> dict[str, Any]:
    """Assess moisture levels and verify water source connectivity."""
    inp = state.get("input") or {}
    moisture = inp.get("soil_moisture_level", 0.35)
    source_ok = inp.get("water_source_available", True)
    return {
        "log": [f"{UNISPSC_CODE}:monitor_sensor"],
        "soil_moisture_level": moisture,
        "water_source_available": source_ok,
    }


def optimize_flow(state: State) -> dict[str, Any]:
    """Calculate target pressure and evaluate system operational health."""
    moisture = state.get("soil_moisture_level", 0.0)
    source_ok = state.get("water_source_available", False)

    # Higher pressure needed for lower moisture levels
    target_pressure = 45.0 if moisture < 0.2 else 30.0
    health = "operational" if source_ok else "halted_no_water"

    return {
        "log": [f"{UNISPSC_CODE}:optimize_flow"],
        "target_pressure_psi": target_pressure if source_ok else 0.0,
        "system_health_status": health,
    }


def finalize_irrigation_cycle(state: State) -> dict[str, Any]:
    """Construct the final outcome and log completion of the irrigation task."""
    health = state.get("system_health_status", "unknown")
    pressure = state.get("target_pressure_psi", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_irrigation_cycle"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "success" if health == "operational" else "warning",
            "pressure_psi": pressure,
            "system_health": health,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("monitor_sensor", monitor_sensor)
_g.add_node("optimize_flow", optimize_flow)
_g.add_node("finalize_irrigation_cycle", finalize_irrigation_cycle)

_g.add_edge(START, "monitor_sensor")
_g.add_edge("monitor_sensor", "optimize_flow")
_g.add_edge("optimize_flow", "finalize_irrigation_cycle")
_g.add_edge("finalize_irrigation_cycle", END)

graph = _g.compile()
