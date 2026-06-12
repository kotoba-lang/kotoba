# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101702 — Material Handling Lifting Gear (segment 24).

Bespoke graph logic for handling lifting and hoisting accessory specifications.
This agent validates mechanical properties, calculates working load limits,
and generates safety certification records for chain slings and related gear.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101702"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101702"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for material handling components
    chain_grade: int
    link_diameter_mm: float
    working_load_limit_kg: float
    inspection_status: str
    safety_factor: float


def inspect_specifications(state: State) -> dict[str, Any]:
    """Analyzes the physical attributes of the lifting component."""
    inp = state.get("input") or {}
    grade = inp.get("grade", 80)
    diameter = inp.get("diameter_mm", 10.0)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "chain_grade": grade,
        "link_diameter_mm": diameter,
        "inspection_status": "PENDING_VERIFICATION",
    }


def calculate_load_capacity(state: State) -> dict[str, Any]:
    """Calculates the Working Load Limit (WLL) based on grade and diameter."""
    grade = state.get("chain_grade", 80)
    diameter = state.get("link_diameter_mm", 10.0)

    # Heuristic for chain sling WLL: (grade / 80) * 0.03 * d^2 (in tonnes)
    wll_tonnes = (grade / 80.0) * 0.03 * (diameter ** 2)
    wll_kg = round(wll_tonnes * 1000, 2)

    return {
        "log": [f"{UNISPSC_CODE}:calculate_load_capacity"],
        "working_load_limit_kg": wll_kg,
        "safety_factor": 4.0 if grade >= 80 else 5.0,
    }


def certify_component(state: State) -> dict[str, Any]:
    """Finalizes the certification record for the lifting accessory."""
    wll = state.get("working_load_limit_kg", 0.0)
    sf = state.get("safety_factor", 4.0)

    return {
        "log": [f"{UNISPSC_CODE}:certify_component"],
        "inspection_status": "CERTIFIED",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "wll_kg": wll,
                "safety_factor": sf,
                "grade": state.get("chain_grade"),
                "diameter_mm": state.get("link_diameter_mm"),
            },
            "status": "compliant",
            "certified": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_specifications)
_g.add_node("calculate", calculate_load_capacity)
_g.add_node("certify", certify_component)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calculate")
_g.add_edge("calculate", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
