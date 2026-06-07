# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11162003 — Abrasive (segment 11).

Bespoke graph for handling abrasive material specifications, grading,
and safety certification within the Etz Hayyim actor model.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11162003"
UNISPSC_TITLE = "Abrasive"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11162003"


class State(TypedDict, total=False):
    # Core fields
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]

    # Domain-specific fields for Abrasive
    grit_size: int
    material_type: str  # e.g., Diamond, Garnet, Aluminum Oxide
    bond_type: str      # e.g., Vitrified, Resinoid, Metal
    safety_certified: bool
    grade_category: str # Fine, Medium, Coarse


def validate_specification(state: State) -> dict[str, Any]:
    """Validates the technical parameters of the abrasive material."""
    inp = state.get("input") or {}
    grit = inp.get("grit", 0)
    material = inp.get("material", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "grit_size": grit,
        "material_type": material,
        "bond_type": inp.get("bond", "Standard"),
    }


def analyze_grade(state: State) -> dict[str, Any]:
    """Determines the grade category based on grit size."""
    grit = state.get("grit_size", 0)

    if grit >= 220:
        grade = "Fine"
    elif grit >= 60:
        grade = "Medium"
    elif grit > 0:
        grade = "Coarse"
    else:
        grade = "N/A"

    # Mock safety check based on material being known
    safe = state.get("material_type") != "Unknown"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_grade"],
        "grade_category": grade,
        "safety_certified": safe,
    }


def finalize_asset(state: State) -> dict[str, Any]:
    """Emits the final verified abrasive asset record."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "grit": state.get("grit_size"),
                "material": state.get("material_type"),
                "grade": state.get("grade_category"),
                "certified": state.get("safety_certified"),
            },
            "status": "verified" if state.get("safety_certified") else "pending_review",
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specification)
_g.add_node("analyze", analyze_grade)
_g.add_node("finalize", finalize_asset)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
