# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14100000 — Paper Materials and Products (segment 14).

Bespoke logic for handling paper-based material workflows, including
specification verification and sustainability evaluation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14100000"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14100000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Paper Materials
    material_grade: str
    gsm_weight: int
    sustainability_rating: float
    is_recyclable: bool


def verify_specifications(state: State) -> dict[str, Any]:
    """Validates the physical properties of the paper material."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "standard")
    gsm = inp.get("gsm", 80)

    return {
        "log": [f"{UNISPSC_CODE}:verify_specifications -> grade:{grade}, gsm:{gsm}"],
        "material_grade": grade,
        "gsm_weight": gsm,
    }


def evaluate_sustainability(state: State) -> dict[str, Any]:
    """Assesses the environmental impact and recyclability."""
    grade = state.get("material_grade", "standard")

    # Simple logic: coated papers or specific grades might be less recyclable
    recyclable = grade.lower() not in ["plastic-coated", "waxed"]
    rating = 0.9 if recyclable else 0.4

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_sustainability -> recyclable:{recyclable}"],
        "is_recyclable": recyclable,
        "sustainability_rating": rating,
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Generates the final agent result for the paper product."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "grade": state.get("material_grade"),
                "gsm": state.get("gsm_weight"),
                "recyclable": state.get("is_recyclable"),
                "sustainability_index": state.get("sustainability_rating"),
            },
            "status": "verified",
        },
    }


_g = StateGraph(State)

_g.add_node("verify_specifications", verify_specifications)
_g.add_node("evaluate_sustainability", evaluate_sustainability)
_g.add_node("finalize_inventory", finalize_inventory)

_g.add_edge(START, "verify_specifications")
_g.add_edge("verify_specifications", "evaluate_sustainability")
_g.add_edge("evaluate_sustainability", "finalize_inventory")
_g.add_edge("finalize_inventory", END)

graph = _g.compile()
