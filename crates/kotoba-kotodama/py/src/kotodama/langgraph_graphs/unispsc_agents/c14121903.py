# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14121903 — Container (segment 14).
Bespoke logic for paper-based industrial container specification and testing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14121903"
UNISPSC_TITLE = "Container"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14121903"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for paper containers
    burst_strength_kpa: int
    flute_type: str
    recycled_content: float
    dimensions_verified: bool
    moisture_resistance_rating: int


def validate_material(state: State) -> dict[str, Any]:
    """Validates paper material properties and flute specifications."""
    inp = state.get("input") or {}
    flute = inp.get("flute", "B-Flute")
    recycled = float(inp.get("recycled_percent", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_material"],
        "flute_type": flute,
        "recycled_content": recycled,
        "dimensions_verified": "length" in inp and "width" in inp,
    }


def stress_test_simulation(state: State) -> dict[str, Any]:
    """Simulates physical stress tests based on material specifications."""
    flute = state.get("flute_type", "Standard")

    # Calculate a mock burst strength
    base_strength = 200
    if flute == "C-Flute":
        base_strength = 250
    elif flute == "A-Flute":
        base_strength = 300

    return {
        "log": [f"{UNISPSC_CODE}:stress_test_simulation"],
        "burst_strength_kpa": base_strength,
        "moisture_resistance_rating": 70 if state.get("recycled_content", 0) < 50 else 50,
    }


def emit_certification(state: State) -> dict[str, Any]:
    """Emits the final container certification and metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "flute": state.get("flute_type"),
                "burst_strength": state.get("burst_strength_kpa"),
                "moisture_rating": state.get("moisture_resistance_rating"),
            },
            "verified": state.get("dimensions_verified", False),
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_material)
_g.add_node("test", stress_test_simulation)
_g.add_node("emit", emit_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "test")
_g.add_edge("test", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
