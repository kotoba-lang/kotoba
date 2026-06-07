# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141011"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141011"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Mining/Drilling machinery
    drill_depth_meters: float
    rock_density_kappa: float
    bit_integrity_score: int
    cooling_fluid_pressure: float
    safety_interlock_engaged: bool


def pre_drill_inspection(state: State) -> dict[str, Any]:
    """Verify safety systems and initial hardware status."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:pre_drill_inspection"],
        "safety_interlock_engaged": inp.get("manual_override") is not True,
        "bit_integrity_score": int(inp.get("initial_bit_score", 100)),
    }


def calibrate_drill_head(state: State) -> dict[str, Any]:
    """Adjust drilling parameters based on rock density inputs."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_drill_head"],
        "rock_density_kappa": float(inp.get("site_density", 2.7)),
        "cooling_fluid_pressure": 45.5,
    }


def execute_drilling_cycle(state: State) -> dict[str, Any]:
    """Simulate a drilling depth increase and aggregate results."""
    density = state.get("rock_density_kappa", 1.0)
    safety = state.get("safety_interlock_engaged", False)
    depth = 0.0

    if safety:
        # Simplified depth calculation based on rock resistance
        depth = 150.0 / (density if density > 0 else 1.0)

    return {
        "log": [f"{UNISPSC_CODE}:execute_drilling_cycle"],
        "drill_depth_meters": depth,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "final_depth": depth,
                "safety_ok": safety,
                "integrity": state.get("bit_integrity_score"),
            },
            "ok": safety,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", pre_drill_inspection)
_g.add_node("calibrate", calibrate_drill_head)
_g.add_node("drill", execute_drilling_cycle)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calibrate")
_g.add_edge("calibrate", "drill")
_g.add_edge("drill", END)

graph = _g.compile()
