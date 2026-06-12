# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20102001 — Lubrication (segment 20).
Bespoke logic for monitoring and managing industrial lubrication health.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20102001"
UNISPSC_TITLE = "Lubrication"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20102001"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Lubrication
    viscosity_index: float
    contamination_level: float
    temperature_celsius: float
    service_priority: str


def check_fluid_properties(state: State) -> dict[str, Any]:
    """Inspects the lubricant's physical properties from telemetry."""
    inp = state.get("input") or {}
    # Extract viscosity and temperature, defaulting to nominal values
    v_idx = float(inp.get("viscosity_cst", 100.0))
    temp = float(inp.get("temp_c", 45.0))

    return {
        "log": [f"{UNISPSC_CODE}:check_fluid_properties"],
        "viscosity_index": v_idx,
        "temperature_celsius": temp,
    }


def analyze_contamination(state: State) -> dict[str, Any]:
    """Evaluates particle count and moisture levels."""
    inp = state.get("input") or {}
    particles = float(inp.get("iso_code_limit", 18.0))
    moisture = float(inp.get("moisture_ppm", 100.0))

    # Simple heuristic for contamination level
    c_lvl = (particles * 0.5) + (moisture * 0.01)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_contamination"],
        "contamination_level": c_lvl,
    }


def determine_servicing(state: State) -> dict[str, Any]:
    """Finalizes the lubrication status and maintenance recommendation."""
    v_idx = state.get("viscosity_index", 100.0)
    c_lvl = state.get("contamination_level", 0.0)
    temp = state.get("temperature_celsius", 45.0)

    # Determine priority based on threshold breaches
    if c_lvl > 15.0 or v_idx < 70.0 or temp > 90.0:
        priority = "CRITICAL"
    elif c_lvl > 10.0 or v_idx < 85.0:
        priority = "ELEVATED"
    else:
        priority = "NORMAL"

    return {
        "log": [f"{UNISPSC_CODE}:determine_servicing"],
        "service_priority": priority,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "analysis": {
                "viscosity_status": "OK" if v_idx >= 85.0 else "DEGRADED",
                "contamination_status": "CLEAN" if c_lvl <= 10.0 else "DIRTY",
                "thermal_status": "STABLE" if temp <= 80.0 else "OVERHEAT"
            },
            "priority": priority,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", check_fluid_properties)
_g.add_node("analyze", analyze_contamination)
_g.add_node("status", determine_servicing)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "analyze")
_g.add_edge("analyze", "status")
_g.add_edge("status", END)

graph = _g.compile()
