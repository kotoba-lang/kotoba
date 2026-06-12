# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111935 — Pole (segment 25).
Bespoke implementation for structural display fixtures and poles.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111935"
UNISPSC_TITLE = "Pole"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111935"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material_grade: str
    height_mm: int
    finish_type: str
    load_limit_kg: float
    safety_certified: bool


def assess_requirements(state: State) -> dict[str, Any]:
    """Analyzes physical requirements for the display pole."""
    inp = state.get("input") or {}
    material = inp.get("material", "6061 Aluminum")
    height = int(inp.get("height", 2400))

    log_entry = f"{UNISPSC_CODE}:assess_requirements(mat={material}, h={height})"
    return {
        "log": [log_entry],
        "material_grade": material,
        "height_mm": height,
    }


def engineering_analysis(state: State) -> dict[str, Any]:
    """Calculates structural limits based on dimensions and material."""
    material = state.get("material_grade", "Steel")
    height = state.get("height_mm", 0)

    # Heuristic for load capacity
    base_capacity = 250.0 if "Steel" in material else 120.0
    # Height penalty: capacity drops as height increases
    capacity = base_capacity * (1000 / max(height, 1000))

    finish = "Anodized" if "Aluminum" in material else "Powder Coated"

    log_entry = f"{UNISPSC_CODE}:engineering_analysis(capacity={capacity:.1f}kg)"
    return {
        "log": [log_entry],
        "load_limit_kg": round(capacity, 2),
        "finish_type": finish,
        "safety_certified": capacity > 20.0,
    }


def finalize_specification(state: State) -> dict[str, Any]:
    """Produces the final technical specification record."""
    spec = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "technical_data": {
            "material": state.get("material_grade"),
            "height_mm": state.get("height_mm"),
            "finish": state.get("finish_type"),
            "max_load_kg": state.get("load_limit_kg"),
        },
        "compliance": {
            "certified": state.get("safety_certified", False),
            "standard": "ISO-2511-FIXTURE"
        }
    }
    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification"],
        "result": spec,
    }


_g = StateGraph(State)
_g.add_node("assess_requirements", assess_requirements)
_g.add_node("engineering_analysis", engineering_analysis)
_g.add_node("finalize_specification", finalize_specification)

_g.add_edge(START, "assess_requirements")
_g.add_edge("assess_requirements", "engineering_analysis")
_g.add_edge("engineering_analysis", "finalize_specification")
_g.add_edge("finalize_specification", END)

graph = _g.compile()
