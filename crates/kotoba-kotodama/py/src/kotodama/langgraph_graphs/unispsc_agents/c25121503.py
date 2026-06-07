# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25121503 — Locomotive (segment 25).
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25121503"
UNISPSC_TITLE = "Locomotive"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25121503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Locomotive
    locomotive_model: str
    tractive_effort_kn: float
    fuel_system_status: str
    track_gauge_compatibility: str
    is_ready_for_service: bool


def inspect_systems(state: State) -> dict[str, Any]:
    """Validate mechanical and safety systems of the locomotive unit."""
    inp = state.get("input") or {}
    model = inp.get("model", "GE-Evolution-Series")
    gauge = inp.get("gauge", "Standard")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_systems"],
        "locomotive_model": model,
        "track_gauge_compatibility": gauge,
        "fuel_system_status": "nominal",
    }


def optimize_power_config(state: State) -> dict[str, Any]:
    """Configure traction and power parameters based on model specs."""
    model = state.get("locomotive_model", "Standard")
    # Simulate traction calculation
    effort = 500.0 if "Heavy" in model else 350.0
    return {
        "log": [f"{UNISPSC_CODE}:optimize_power_config"],
        "tractive_effort_kn": effort,
        "is_ready_for_service": True,
    }


def finalize_dispatch(state: State) -> dict[str, Any]:
    """Authorize the locomotive for mainline or yard service."""
    ready = state.get("is_ready_for_service", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_dispatch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "dispatched": ready,
            "manifest": {
                "model": state.get("locomotive_model"),
                "traction_kn": state.get("tractive_effort_kn"),
                "gauge": state.get("track_gauge_compatibility"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_systems", inspect_systems)
_g.add_node("optimize_power_config", optimize_power_config)
_g.add_node("finalize_dispatch", finalize_dispatch)

_g.add_edge(START, "inspect_systems")
_g.add_edge("inspect_systems", "optimize_power_config")
_g.add_edge("optimize_power_config", "finalize_dispatch")
_g.add_edge("finalize_dispatch", END)

graph = _g.compile()
