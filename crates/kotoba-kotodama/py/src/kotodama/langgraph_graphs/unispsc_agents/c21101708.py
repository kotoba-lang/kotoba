# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101708 — Planters (segment 21).

Bespoke graph logic for managing agricultural planter machinery operations,
including seed configuration, depth calibration, and mission execution.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101708"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101708"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for agricultural planter machinery
    seed_variety: str
    target_depth_cm: float
    hopper_level_pct: float
    calibration_status: str
    gps_signal_verified: bool


def initialize_planter(state: State) -> dict[str, Any]:
    """Prepares the planter hardware state based on mission input."""
    inp = state.get("input") or {}
    seed = inp.get("seed", "corn_hybrid_a")
    fill = float(inp.get("hopper_fill", 100.0))

    return {
        "log": [f"{UNISPSC_CODE}:initialize_planter"],
        "seed_variety": seed,
        "hopper_level_pct": fill,
        "gps_signal_verified": inp.get("gps_lock", True),
        "calibration_status": "pending"
    }


def calibrate_depth_parameters(state: State) -> dict[str, Any]:
    """Calculates and sets the mechanical depth based on seed variety."""
    variety = state.get("seed_variety", "standard")

    # Logic: deeper for corn, shallower for smaller seeds
    if "corn" in variety.lower():
        depth = 5.5
    elif "soy" in variety.lower():
        depth = 3.5
    else:
        depth = 4.0

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_depth_parameters"],
        "target_depth_cm": depth,
        "calibration_status": "calibrated"
    }


def execute_planting_mission(state: State) -> dict[str, Any]:
    """Finalizes the planting operation and emits telemetry results."""
    is_calibrated = state.get("calibration_status") == "calibrated"
    has_gps = state.get("gps_signal_verified", False)
    has_seed = state.get("hopper_level_pct", 0) > 5.0

    operational_ok = is_calibrated and has_gps and has_seed

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "operational_status": "READY" if operational_ok else "FAULT",
        "telemetry": {
            "depth_setting": state.get("target_depth_cm"),
            "seed_type": state.get("seed_variety"),
            "hopper_reserve": state.get("hopper_level_pct")
        },
        "ok": operational_ok,
    }

    return {
        "log": [f"{UNISPSC_CODE}:execute_planting_mission"],
        "result": res
    }


_g = StateGraph(State)

_g.add_node("initialize", initialize_planter)
_g.add_node("calibrate", calibrate_depth_parameters)
_g.add_node("execute", execute_planting_mission)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "calibrate")
_g.add_edge("calibrate", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
