# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11161502"
UNISPSC_TITLE = "Mining"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11161502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    mineral_type: str
    mine_depth_m: int
    safety_clearance: bool
    recovery_rate: float


def survey(state: State) -> dict[str, Any]:
    """Node: Analyze geological conditions for extraction."""
    inp = state.get("input") or {}
    resource = inp.get("resource", "Copper")
    depth = inp.get("target_depth", 800)

    # Simulation: Extremely deep mines require specialized equipment not modeled here
    cleared = depth < 3000

    return {
        "log": [f"{UNISPSC_CODE}:survey -> target={resource}, depth={depth}m"],
        "mineral_type": resource,
        "mine_depth_m": depth,
        "safety_clearance": cleared,
    }


def extract(state: State) -> dict[str, Any]:
    """Node: Execute extraction protocol if safety is verified."""
    if not state.get("safety_clearance"):
        return {
            "log": [f"{UNISPSC_CODE}:extract -> ABORTED (Safety Violation)"],
            "recovery_rate": 0.0,
        }

    # Simulated recovery rate based on depth and resource complexity
    depth = state.get("mine_depth_m", 0)
    rate = 0.88 if depth < 1000 else 0.75

    return {
        "log": [f"{UNISPSC_CODE}:extract -> SUCCESS (rate={rate})"],
        "recovery_rate": rate,
    }


def audit(state: State) -> dict[str, Any]:
    """Node: Finalize results and produce the output manifest."""
    rate = state.get("recovery_rate", 0.0)
    mineral = state.get("mineral_type", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:audit -> record finalized"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "commodity": mineral,
            "recovery": rate,
            "status": "COMPLETED" if rate > 0 else "FAILED",
            "ok": rate > 0,
            "did": UNISPSC_DID,
        },
    }


_g = StateGraph(State)
_g.add_node("survey", survey)
_g.add_node("extract", extract)
_g.add_node("audit", audit)

_g.add_edge(START, "survey")
_g.add_edge("survey", "extract")
_g.add_edge("extract", "audit")
_g.add_edge("audit", END)

graph = _g.compile()
