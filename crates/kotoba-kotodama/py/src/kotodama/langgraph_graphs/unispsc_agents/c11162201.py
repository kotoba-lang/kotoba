# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11162201 — Material (segment 11).

Bespoke LangGraph implementation for material classification and validation
within the mineral, textile, and inedible plant/animal materials segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11162201"
UNISPSC_TITLE = "Material"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11162201"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for "Material"
    material_category: str
    purity_level: float
    batch_reference: str
    safety_validated: bool
    inspection_passed: bool


def inspect_material(state: State) -> dict[str, Any]:
    """Validates the raw material attributes and safety standards."""
    inp = state.get("input") or {}
    purity = inp.get("purity", 0.0)
    is_hazardous = inp.get("hazardous", False)

    passed = purity > 0.8 and not is_hazardous

    return {
        "log": [f"{UNISPSC_CODE}:inspect_material"],
        "purity_level": purity,
        "inspection_passed": passed,
        "safety_validated": not is_hazardous
    }


def categorize_material(state: State) -> dict[str, Any]:
    """Determines the specific category based on material properties."""
    inp = state.get("input") or {}
    raw_type = inp.get("type", "unknown")

    # Simple classification logic based on purity
    grade = "industrial" if state.get("purity_level", 0) > 0.95 else "standard"

    return {
        "log": [f"{UNISPSC_CODE}:categorize_material"],
        "material_category": f"{raw_type}_{grade}",
        "batch_reference": inp.get("batch", "BATCH-DEFAULT")
    }


def finalize_material_record(state: State) -> dict[str, Any]:
    """Generates the final structured response for the material agent."""
    success = state.get("inspection_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_material_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "category": state.get("material_category"),
            "batch": state.get("batch_reference"),
            "status": "APPROVED" if success else "REJECTED",
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_material)
_g.add_node("categorize", categorize_material)
_g.add_node("finalize", finalize_material_record)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "categorize")
_g.add_edge("categorize", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
