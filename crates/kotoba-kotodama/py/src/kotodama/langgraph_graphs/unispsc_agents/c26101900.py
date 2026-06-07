# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101900"
UNISPSC_TITLE = "Engine"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101900"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    engine_type: str
    thermal_efficiency: float
    cycle_count: int
    safety_override_active: bool


def ingest_engine_data(state: State) -> dict[str, Any]:
    """Validates and parses incoming engine specifications."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:ingest_engine_data"],
        "engine_type": inp.get("type", "internal_combustion"),
        "cycle_count": inp.get("cycles", 0),
    }


def analyze_performance(state: State) -> dict[str, Any]:
    """Performs simulated performance and thermal analysis based on usage cycles."""
    cycles = state.get("cycle_count", 0)
    # Simulate efficiency degradation over time
    efficiency = 0.88 if cycles < 500 else 0.75
    return {
        "log": [f"{UNISPSC_CODE}:analyze_performance"],
        "thermal_efficiency": efficiency,
        "safety_override_active": cycles > 10000,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Generates the final engine status and compliance report."""
    efficiency = state.get("thermal_efficiency", 0.0)
    is_safe = not state.get("safety_override_active", False)

    status = "REJECTED"
    if is_safe:
        status = "CERTIFIED" if efficiency > 0.8 else "OPERATIONAL"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "engine_status": status,
            "efficiency_metrics": {"rating": efficiency},
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_engine_data)
_g.add_node("analyze", analyze_performance)
_g.add_node("finalize", finalize_certification)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
