# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101806 — Sprayer (segment 21).

Bespoke logic for controlling and monitoring industrial spraying equipment.
Handles pressure calibration, fluid level monitoring, and nozzle status tracking.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101806"
UNISPSC_TITLE = "Sprayer"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101806"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Sprayer
    pressure_psi: float
    tank_level_pct: float
    nozzle_type: str
    is_active: bool


def configure_sprayer(state: State) -> dict[str, Any]:
    """Initializes the sprayer with provided or default configuration."""
    inp = state.get("input") or {}
    nozzle = inp.get("nozzle", "hollow-cone")
    initial_level = inp.get("initial_level", 100.0)

    return {
        "log": [f"{UNISPSC_CODE}:configure_sprayer"],
        "nozzle_type": nozzle,
        "tank_level_pct": initial_level,
        "is_active": False,
    }


def calibrate_pressure(state: State) -> dict[str, Any]:
    """Calibrates the operating pressure based on nozzle and flow targets."""
    inp = state.get("input") or {}
    target_flow = inp.get("target_flow", 2.0)

    # Simulated calibration logic: psi = 50 * flow
    calibrated_psi = target_flow * 50.0

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_pressure"],
        "pressure_psi": calibrated_psi,
    }


def execute_spraying(state: State) -> dict[str, Any]:
    """Simulates the spraying process and updates equipment status."""
    psi = state.get("pressure_psi", 0.0)
    level = state.get("tank_level_pct", 0.0)

    # Consumption simulation
    new_level = max(0.0, level - 10.0)
    operational = psi > 0 and level > 0

    return {
        "log": [f"{UNISPSC_CODE}:execute_spraying"],
        "tank_level_pct": new_level,
        "is_active": operational,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operational": operational,
            "final_pressure": psi,
            "remaining_fluid": new_level,
        },
    }


_g = StateGraph(State)

_g.add_node("configure", configure_sprayer)
_g.add_node("calibrate", calibrate_pressure)
_g.add_node("execute", execute_spraying)

_g.add_edge(START, "configure")
_g.add_edge("configure", "calibrate")
_g.add_edge("calibrate", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
