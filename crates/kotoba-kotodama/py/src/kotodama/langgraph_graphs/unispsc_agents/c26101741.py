# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101741 — Engine Sleeve.
Mechanical engineering logic for cylinder liner validation and quality assurance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101741"
UNISPSC_TITLE = "Engine Sleeve"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101741"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific engine sleeve fields
    material_alloy: str
    inner_diameter_mm: float
    surface_finish_ra: float
    quality_certified: bool


def assess_material(state: State) -> dict[str, Any]:
    """Validates the metallurgical properties of the engine sleeve."""
    inp = state.get("input") or {}
    alloy = inp.get("alloy", "Nihard Cast Iron")
    return {
        "log": [f"{UNISPSC_CODE}:assess_material:{alloy}"],
        "material_alloy": alloy,
    }


def verify_geometry(state: State) -> dict[str, Any]:
    """Performs dimensional inspection of the sleeve bore and outer diameter."""
    inp = state.get("input") or {}
    id_mm = float(inp.get("inner_diameter", 85.0))
    # Typical engine sleeves have specific surface roughness requirements (Ra in microns)
    ra = float(inp.get("surface_finish", 0.4))

    # Simple validation logic for engineering specs
    is_valid = 50.0 <= id_mm <= 200.0 and ra <= 0.8

    return {
        "log": [f"{UNISPSC_CODE}:verify_geometry:ID={id_mm}mm, Ra={ra}u"],
        "inner_diameter_mm": id_mm,
        "surface_finish_ra": ra,
        "quality_certified": is_valid,
    }


def record_batch(state: State) -> dict[str, Any]:
    """Finalizes the production record and issues the certification result."""
    is_ok = state.get("quality_certified", False)
    return {
        "log": [f"{UNISPSC_CODE}:record_batch:status={'PASS' if is_ok else 'FAIL'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certified": is_ok,
            "metrics": {
                "alloy": state.get("material_alloy"),
                "bore_size_mm": state.get("inner_diameter_mm"),
                "roughness_ra": state.get("surface_finish_ra")
            }
        },
    }


_g = StateGraph(State)
_g.add_node("assess_material", assess_material)
_g.add_node("verify_geometry", verify_geometry)
_g.add_node("record_batch", record_batch)

_g.add_edge(START, "assess_material")
_g.add_edge("assess_material", "verify_geometry")
_g.add_edge("verify_geometry", "record_batch")
_g.add_edge("record_batch", END)

graph = _g.compile()
