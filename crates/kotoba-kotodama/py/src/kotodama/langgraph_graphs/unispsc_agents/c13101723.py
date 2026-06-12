# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13101723 — Abrasive (segment 13).

Bespoke graph logic for abrasive material handling, including grit size validation,
material hardness assessment, and safety certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13101723"
UNISPSC_TITLE = "Abrasive"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13101723"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Abrasives
    grit_size: int
    material_type: str
    mohs_hardness: float
    safety_certified: bool
    batch_verified: bool


def validate_specification(state: State) -> dict[str, Any]:
    """Validates the abrasive specifications against industrial standards."""
    inp = state.get("input") or {}
    grit = inp.get("grit", 80)
    material = inp.get("material", "aluminum oxide")

    # Simulate validation logic
    is_valid = grit > 0 and len(material) > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "grit_size": grit,
        "material_type": material,
        "batch_verified": is_valid
    }


def assess_hardness(state: State) -> dict[str, Any]:
    """Determines the Mohs hardness based on the material type."""
    material = state.get("material_type", "").lower()

    # Mock hardness lookup
    hardness_map = {
        "diamond": 10.0,
        "silicon carbide": 9.5,
        "aluminum oxide": 9.0,
        "garnet": 7.5,
        "quartz": 7.0
    }
    hardness = hardness_map.get(material, 5.0)

    return {
        "log": [f"{UNISPSC_CODE}:assess_hardness"],
        "mohs_hardness": hardness,
        "safety_certified": hardness > 0
    }


def certify_and_emit(state: State) -> dict[str, Any]:
    """Finalizes the abrasive actor state and emits the result."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_and_emit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "grit": state.get("grit_size"),
                "material": state.get("material_type"),
                "hardness": state.get("mohs_hardness")
            },
            "status": "certified" if state.get("safety_certified") else "pending",
            "ok": state.get("batch_verified", False)
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specification)
_g.add_node("assess", assess_hardness)
_g.add_node("emit", certify_and_emit)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
