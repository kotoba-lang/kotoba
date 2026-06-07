# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24122003 — Glass Bottle (segment 24).

This bespoke implementation handles the state transitions for glass bottle
manufacturing specifications, including material validation and annealing quality.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24122003"
UNISPSC_TITLE = "Glass Bottle"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24122003"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain state for Glass Bottle
    composition: str
    capacity_ml: int
    is_annealed: bool
    quality_grade: str


def validate_specification(state: State) -> dict[str, Any]:
    """Validates the glass composition and capacity requirements."""
    inp = state.get("input") or {}
    composition = inp.get("composition", "soda-lime")
    capacity = inp.get("capacity_ml", 750)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "composition": composition,
        "capacity_ml": capacity,
    }


def process_annealing(state: State) -> dict[str, Any]:
    """Simulates the annealing process to remove internal stresses from the glass."""
    composition = state.get("composition", "soda-lime")
    # Annealing is a critical thermal treatment for bottle durability
    is_annealed = composition in ["borosilicate", "soda-lime", "flint"]

    return {
        "log": [f"{UNISPSC_CODE}:process_annealing"],
        "is_annealed": is_annealed,
        "quality_grade": "Grade-A" if composition == "borosilicate" else "Standard",
    }


def emit_product_record(state: State) -> dict[str, Any]:
    """Finalizes the glass bottle record and prepares the output result."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_product_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specifications": {
                "composition": state.get("composition"),
                "capacity_ml": state.get("capacity_ml"),
                "thermal_treatment": "annealed" if state.get("is_annealed") else "raw",
                "grade": state.get("quality_grade"),
            },
            "status": "production_ready",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specification)
_g.add_node("anneal", process_annealing)
_g.add_node("emit", emit_product_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "anneal")
_g.add_edge("anneal", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
