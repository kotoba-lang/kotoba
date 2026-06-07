# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10121802"
UNISPSC_TITLE = "Excavation"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10121802"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    site_survey_completed: bool
    soil_type: str
    target_depth_m: float
    depth_reached_m: float
    safety_clearance: bool


def survey_site(state: State) -> dict[str, Any]:
    """Inspect the site and determine soil conditions."""
    inp = state.get("input") or {}
    soil = inp.get("soil_type", "loam")
    target = float(inp.get("target_depth", 3.5))
    return {
        "log": [f"{UNISPSC_CODE}:survey_site -> {soil}"],
        "site_survey_completed": True,
        "soil_type": soil,
        "target_depth_m": target,
        "safety_clearance": inp.get("safety_clearance", True),
    }


def execute_excavation(state: State) -> dict[str, Any]:
    """Perform the physical excavation work."""
    if not state.get("safety_clearance"):
        return {"log": [f"{UNISPSC_CODE}:excavation_halted_safety"]}

    depth = state.get("target_depth_m", 0.0)
    return {
        "log": [f"{UNISPSC_CODE}:excavating_to_{depth}m"],
        "depth_reached_m": depth,
    }


def finalize_work(state: State) -> dict[str, Any]:
    """Verify work against target and emit completion state."""
    reached = state.get("depth_reached_m", 0.0)
    target = state.get("target_depth_m", 1.0)
    success = reached >= target

    return {
        "log": [f"{UNISPSC_CODE}:finalize_work"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "completed" if success else "incomplete",
            "final_depth": reached,
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("survey_site", survey_site)
_g.add_node("execute_excavation", execute_excavation)
_g.add_node("finalize_work", finalize_work)

_g.add_edge(START, "survey_site")
_g.add_edge("survey_site", "execute_excavation")
_g.add_edge("execute_excavation", "finalize_work")
_g.add_edge("finalize_work", END)

graph = _g.compile()
