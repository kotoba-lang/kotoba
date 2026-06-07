# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12162003 — Material.

Bespoke graph logic for earth-based material assessment. This agent validates
material composition, analyzes moisture and impurity levels, and records
the resulting compliance state.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12162003"
UNISPSC_TITLE = "Material"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12162003"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    moisture_level: float
    impurity_pct: float
    texture_grade: str
    is_compliant: bool


def inspect_material(state: State) -> dict[str, Any]:
    """Initial inspection of the material batch metadata."""
    inp = state.get("input") or {}
    # Simulate extraction of physical properties from input
    moisture = float(inp.get("moisture", 5.0))
    impurities = float(inp.get("impurities", 0.5))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_material"],
        "moisture_level": moisture,
        "impurity_pct": impurities,
    }


def analyze_composition(state: State) -> dict[str, Any]:
    """Assess the material grade and compliance based on properties."""
    moisture = state.get("moisture_level", 0.0)
    impurities = state.get("impurity_pct", 0.0)

    # Logic: High moisture or impurities reduce quality
    grade = "Standard"
    if moisture < 2.0 and impurities < 0.1:
        grade = "Premium"
    elif moisture > 15.0 or impurities > 2.0:
        grade = "Industrial"

    compliant = impurities < 5.0 # Basic safety threshold

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition"],
        "texture_grade": grade,
        "is_compliant": compliant,
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Format the final result for the material actor."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "analysis": {
                "grade": state.get("texture_grade"),
                "compliant": state.get("is_compliant"),
                "moisture": state.get("moisture_level"),
            },
            "ok": state.get("is_compliant", False),
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_material)
_g.add_node("analyze", analyze_composition)
_g.add_node("finalize", finalize_record)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
