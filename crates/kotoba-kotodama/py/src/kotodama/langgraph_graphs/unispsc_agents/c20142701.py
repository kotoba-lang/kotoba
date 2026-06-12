# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20142701 — Fastener (segment 20).

Bespoke LangGraph implementation for Fastener verification logic.
This agent handles specification validation and mechanical property verification
for industrial fasteners used in mining and drilling equipment.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20142701"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20142701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Fastener
    material_grade: str
    coating_type: str
    tensile_strength_verified: bool
    dimensions_verified: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the input fastener specifications and material grade."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "Grade 8.8")
    coating = inp.get("coating", "Galvanized")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs -> {grade}, {coating}"],
        "material_grade": grade,
        "coating_type": coating,
    }


def check_mechanicals(state: State) -> dict[str, Any]:
    """Verifies mechanical properties like tensile strength for the specified grade."""
    grade = state.get("material_grade", "Grade 8.8")
    # Simulation: verify if the grade meets the segment 20 standard
    verified = grade.startswith("Grade") or grade.startswith("A")

    return {
        "log": [f"{UNISPSC_CODE}:check_mechanicals -> verified={verified}"],
        "tensile_strength_verified": verified,
        "dimensions_verified": True,
    }


def emit_manifest(state: State) -> dict[str, Any]:
    """Generates the final certification manifest for the fastener batch."""
    is_ok = state.get("tensile_strength_verified", False) and state.get("dimensions_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": is_ok,
            "metadata": {
                "grade": state.get("material_grade"),
                "coating": state.get("coating_type"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("check", check_mechanicals)
_g.add_node("emit", emit_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "check")
_g.add_edge("check", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
