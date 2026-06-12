# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153035 — Laser Welding (segment 23).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153035"
UNISPSC_TITLE = "Laser Welding"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153035"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    laser_power_watts: int
    beam_velocity_mms: float
    focal_position_mm: float
    shielding_gas_flow_lpm: float
    thermal_gradient_k: float


def setup_laser_parameters(state: State) -> dict[str, Any]:
    """Configures the laser hardware settings based on input requirements."""
    inp = state.get("input") or {}
    power = inp.get("requested_power", 3200)
    velocity = inp.get("speed", 20.0)

    return {
        "log": [f"{UNISPSC_CODE}:setup_laser_parameters"],
        "laser_power_watts": power,
        "beam_velocity_mms": velocity,
        "focal_position_mm": -1.2,
        "shielding_gas_flow_lpm": 25.0
    }


def execute_weld_pass(state: State) -> dict[str, Any]:
    """Simulates the physical welding process and calculates thermal state."""
    power = state.get("laser_power_watts", 0)
    velocity = state.get("beam_velocity_mms", 1.0)

    # Calculate simulated thermal gradient based on power density
    gradient = (power / velocity) * 0.15

    return {
        "log": [f"{UNISPSC_CODE}:execute_weld_pass"],
        "thermal_gradient_k": round(gradient, 2)
    }


def validate_weld_quality(state: State) -> dict[str, Any]:
    """Inspects the resulting weld integrity and finalizes state."""
    gradient = state.get("thermal_gradient_k", 0.0)
    # Define an optimal thermal window for structural integrity
    is_optimal = 150.0 < gradient < 600.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_weld_quality"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "thermal_metric": gradient,
            "quality_assessment": "CERTIFIED" if is_optimal else "OUT_OF_SPEC",
            "ok": is_optimal,
        },
    }


_g = StateGraph(State)
_g.add_node("setup", setup_laser_parameters)
_g.add_node("weld", execute_weld_pass)
_g.add_node("validate", validate_weld_quality)

_g.add_edge(START, "setup")
_g.add_edge("setup", "weld")
_g.add_edge("weld", "validate")
_g.add_edge("validate", END)

graph = _g.compile()
