# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25201603 — Terrain System (segment 25).

Bespoke graph logic for vehicle terrain-response systems, handling suspension
adjustments and traction control parameters based on surface analysis.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201603"
UNISPSC_TITLE = "Terrain System"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201603"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific state for Terrain System
    ground_clearance_mm: int
    damping_coefficient: float
    traction_mode: str
    surface_type: str
    sensor_health: bool


def analyze_surface(state: State) -> dict[str, Any]:
    """Analyzes input sensor data to determine the current terrain surface."""
    inp = state.get("input") or {}
    surface = inp.get("surface", "asphalt")
    health = inp.get("sensor_ready", True)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_surface -> {surface}"],
        "surface_type": surface,
        "sensor_health": health,
    }


def configure_suspension(state: State) -> dict[str, Any]:
    """Adjusts ground clearance and damping based on surface type."""
    surface = state.get("surface_type", "asphalt")

    if surface == "mud" or surface == "sand":
        clearance = 240
        damping = 0.85
        mode = "OFF-ROAD"
    elif surface == "gravel":
        clearance = 210
        damping = 0.65
        mode = "RUGGED"
    else:
        clearance = 180
        damping = 0.45
        mode = "COMFORT"

    return {
        "log": [f"{UNISPSC_CODE}:configure_suspension -> {mode}"],
        "ground_clearance_mm": clearance,
        "damping_coefficient": damping,
        "traction_mode": mode,
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Generates the final system status for the terrain system."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "system_config": {
                "mode": state.get("traction_mode"),
                "clearance": state.get("ground_clearance_mm"),
                "damping": state.get("damping_coefficient"),
                "operational": state.get("sensor_health", False),
            },
            "ok": state.get("sensor_health", False),
        },
    }


_g = StateGraph(State)

_g.add_node("analyze_surface", analyze_surface)
_g.add_node("configure_suspension", configure_suspension)
_g.add_node("finalize_telemetry", finalize_telemetry)

_g.add_edge(START, "analyze_surface")
_g.add_edge("analyze_surface", "configure_suspension")
_g.add_edge("configure_suspension", "finalize_telemetry")
_g.add_edge("finalize_telemetry", END)

graph = _g.compile()
