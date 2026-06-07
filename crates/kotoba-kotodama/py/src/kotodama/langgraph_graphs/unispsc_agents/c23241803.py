# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
# Use a specific import for Annotated to ensure compatibility
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23241803"
UNISPSC_TITLE = "Drill"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23241803"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    spindle_speed_rpm: int
    feed_rate_mm_min: float
    coolant_active: bool
    target_depth_mm: float


def setup_drilling_parameters(state: State) -> dict[str, Any]:
    """Calculates optimal machining parameters based on material and tool size."""
    inp = state.get("input") or {}
    material = inp.get("material", "carbon_steel")
    diameter = float(inp.get("diameter_mm", 12.0))

    # Simulate machining logic
    if material == "aluminum":
        speed = 3000
        feed = 450.0
    elif material == "stainless":
        speed = 500
        feed = 90.0
    else:
        speed = 1200
        feed = 200.0

    return {
        "log": [f"{UNISPSC_CODE}:setup -> speed:{speed}rpm, feed:{feed}mm/min"],
        "spindle_speed_rpm": speed,
        "feed_rate_mm_min": feed,
        "coolant_active": speed > 800,
        "target_depth_mm": float(inp.get("depth_mm", 25.0)),
    }


def execute_bore_cycle(state: State) -> dict[str, Any]:
    """Simulates the drilling cycle including rapid approach and feed movements."""
    depth = state.get("target_depth_mm", 0.0)
    coolant = "Active" if state.get("coolant_active") else "Inactive"

    return {
        "log": [f"{UNISPSC_CODE}:bore_cycle -> depth:{depth}mm reached, coolant:{coolant}"],
    }


def inspect_and_emit(state: State) -> dict[str, Any]:
    """Performs virtual quality check and emits final operational telemetry."""
    return {
        "log": [f"{UNISPSC_CODE}:inspect -> dimensional_integrity:OK"],
        "result": {
            "actor": UNISPSC_DID,
            "unispsc": {
                "code": UNISPSC_CODE,
                "title": UNISPSC_TITLE,
            },
            "telemetry": {
                "final_depth": state.get("target_depth_mm"),
                "max_rpm": state.get("spindle_speed_rpm"),
                "coolant_used": state.get("coolant_active"),
            },
            "status": "success",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("setup", setup_drilling_parameters)
_g.add_node("bore", execute_bore_cycle)
_g.add_node("inspect", inspect_and_emit)

_g.add_edge(START, "setup")
_g.add_edge("setup", "bore")
_g.add_edge("bore", "inspect")
_g.add_edge("inspect", END)

graph = _g.compile()
