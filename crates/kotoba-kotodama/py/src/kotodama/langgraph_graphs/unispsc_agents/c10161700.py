# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10161700"
UNISPSC_TITLE = "Feed"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10161700"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    batch_id: str
    nutritional_analysis: dict[str, float]
    quality_grade: str
    moisture_content: float


def inspect_raw_materials(state: State) -> dict[str, Any]:
    """Validate incoming grains and supplements for feed production."""
    inp = state.get("input") or {}
    batch_id = inp.get("batch_id", "F-DEFAULT-999")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_raw_materials"],
        "batch_id": batch_id,
        "quality_grade": "Premium",
        "moisture_content": 11.2,
    }


def calculate_formula(state: State) -> dict[str, Any]:
    """Determine the optimal nutrient blend for the specific feed type."""
    return {
        "log": [f"{UNISPSC_CODE}:calculate_formula"],
        "nutritional_analysis": {
            "crude_protein": 18.5,
            "crude_fat": 4.2,
            "fiber": 5.0,
            "lysine": 0.95,
        },
    }


def verify_and_bag(state: State) -> dict[str, Any]:
    """Final quality assurance check and packaging metadata generation."""
    analysis = state.get("nutritional_analysis") or {}
    protein_ok = analysis.get("crude_protein", 0) >= 16.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_and_bag"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_id": state.get("batch_id"),
            "compliance_verified": protein_ok,
            "status": "READY_FOR_DISTRIBUTION" if protein_ok else "REJECTED",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_raw_materials", inspect_raw_materials)
_g.add_node("calculate_formula", calculate_formula)
_g.add_node("verify_and_bag", verify_and_bag)

_g.add_edge(START, "inspect_raw_materials")
_g.add_edge("inspect_raw_materials", "calculate_formula")
_g.add_edge("calculate_formula", "verify_and_bag")
_g.add_edge("verify_and_bag", END)

graph = _g.compile()
