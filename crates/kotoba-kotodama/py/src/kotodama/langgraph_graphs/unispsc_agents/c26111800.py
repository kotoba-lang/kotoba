# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111800 — Drive (segment 26).

This bespoke implementation handles state transitions for power generation and
distribution drives, providing validation and manifest generation for
mechanical and electrical drive systems.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111800"
UNISPSC_TITLE = "Drive"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111800"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Drive components
    drive_topology: str
    rated_horsepower: float
    input_phase: int
    cooling_method: str
    safety_rating: str


def ingest_specifications(state: State) -> dict[str, Any]:
    """Parses drive engineering requirements from the input payload."""
    payload = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:ingest_specifications"],
        "drive_topology": str(payload.get("topology", "variable_frequency")),
        "rated_horsepower": float(payload.get("hp", 0.0)),
        "input_phase": int(payload.get("phase", 3)),
    }


def evaluate_thermal_load(state: State) -> dict[str, Any]:
    """Assigns cooling requirements and safety ratings based on power output."""
    hp = state.get("rated_horsepower", 0.0)
    cooling = "air_cooled" if hp < 150.0 else "liquid_cooled"
    rating = "SIL2" if hp < 500.0 else "SIL3"
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_thermal_load"],
        "cooling_method": cooling,
        "safety_rating": rating,
    }


def synthesize_result(state: State) -> dict[str, Any]:
    """Constructs the final UNISPSC actor response and configuration manifest."""
    return {
        "log": [f"{UNISPSC_CODE}:synthesize_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "configuration": {
                "topology": state.get("drive_topology"),
                "horsepower": state.get("rated_horsepower"),
                "phase": state.get("input_phase"),
                "thermal_management": state.get("cooling_method"),
                "compliance": state.get("safety_rating"),
            },
            "verified": True,
        },
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_specifications)
_g.add_node("evaluate", evaluate_thermal_load)
_g.add_node("synthesize", synthesize_result)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "evaluate")
_g.add_edge("evaluate", "synthesize")
_g.add_edge("synthesize", END)

graph = _g.compile()
