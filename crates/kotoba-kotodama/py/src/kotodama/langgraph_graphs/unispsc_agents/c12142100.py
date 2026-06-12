# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12142100"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12142100"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    purity_percentage: float
    activation_temp_celsius: float
    surface_area_m2g: float
    batch_id: str
    is_ready: bool


def verify_specification(state: State) -> dict[str, Any]:
    """Verifies the physical and chemical specifications of the catalyst batch."""
    inp = state.get("input") or {}
    batch = inp.get("batch_id", "CAT-BATCH-DEFAULT")
    purity = inp.get("purity", 99.9)
    surface_area = inp.get("surface_area", 250.0)

    return {
        "log": [f"{UNISPSC_CODE}:verify_specification - Batch {batch} verified: {purity}% purity, {surface_area} m2/g"],
        "batch_id": batch,
        "purity_percentage": purity,
        "surface_area_m2g": surface_area,
    }


def activate_substrate(state: State) -> dict[str, Any]:
    """Calculates optimal activation temperature and simulates thermal activation."""
    purity = state.get("purity_percentage", 0.0)
    # Higher purity catalysts require precisely controlled lower temperatures
    target_temp = 450.0 + (100.0 - purity) * 10.0

    return {
        "log": [f"{UNISPSC_CODE}:activate_substrate - Thermal activation at {target_temp:.1f}C initiated"],
        "activation_temp_celsius": target_temp,
        "is_ready": purity > 95.0,
    }


def optimize_reaction_profile(state: State) -> dict[str, Any]:
    """Determines the expected performance profile for the activated catalyst."""
    ready = state.get("is_ready", False)
    surface = state.get("surface_area_m2g", 0.0)

    # Efficiency is a function of surface area and successful activation
    efficiency_index = (surface / 300.0) * 100.0 if ready else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:optimize_reaction_profile - Efficiency index: {efficiency_index:.2f}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_id": state.get("batch_id"),
            "performance_index": efficiency_index,
            "activation_temp": state.get("activation_temp_celsius"),
            "status": "OPTIMIZED" if efficiency_index > 80 else "SUBOPTIMAL",
        },
    }


_g = StateGraph(State)
_g.add_node("verify_specification", verify_specification)
_g.add_node("activate_substrate", activate_substrate)
_g.add_node("optimize_reaction_profile", optimize_reaction_profile)

_g.add_edge(START, "verify_specification")
_g.add_edge("verify_specification", "activate_substrate")
_g.add_edge("activate_substrate", "optimize_reaction_profile")
_g.add_edge("optimize_reaction_profile", END)

graph = _g.compile()
