# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20141014 — Gear Spec (segment 20).
Bespoke implementation for mechanical gear specification and validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141014"
UNISPSC_TITLE = "Gear Spec"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141014"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Gear Spec
    gear_type: str
    material_grade: str
    tooth_count: int
    specs_validated: bool
    computed_geometry: dict[str, float]


def validate_requirements(state: State) -> dict[str, Any]:
    """Validate incoming gear specification requests."""
    inp = state.get("input") or {}
    g_type = inp.get("gear_type", "spur")
    t_count = int(inp.get("tooth_count", 0))
    material = inp.get("material", "AISI 4140")

    valid = t_count > 0 and g_type in ["spur", "helical", "bevel", "worm"]

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "gear_type": g_type,
        "tooth_count": t_count,
        "material_grade": material,
        "specs_validated": valid,
    }


def analyze_geometry(state: State) -> dict[str, Any]:
    """Calculate gear geometry based on validated specs."""
    if not state.get("specs_validated"):
        return {"log": [f"{UNISPSC_CODE}:analyze_geometry_skipped"]}

    # Mock geometric calculations for pitch diameter and module
    t_count = state.get("tooth_count", 0)
    pitch_dia = t_count * 2.5  # assuming module 2.5

    return {
        "log": [f"{UNISPSC_CODE}:analyze_geometry"],
        "computed_geometry": {
            "pitch_diameter": float(pitch_dia),
            "module": 2.5,
            "addendum": 2.5,
            "dedendum": 3.125
        }
    }


def generate_spec_report(state: State) -> dict[str, Any]:
    """Finalize the gear specification report."""
    valid = state.get("specs_validated", False)
    geometry = state.get("computed_geometry", {})

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "certified": valid,
        "specifications": {
            "type": state.get("gear_type"),
            "material": state.get("material_grade"),
            "teeth": state.get("tooth_count"),
            "geometry": geometry
        }
    }

    return {
        "log": [f"{UNISPSC_CODE}:generate_spec_report"],
        "result": res
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requirements)
_g.add_node("analyze", analyze_geometry)
_g.add_node("finalize", generate_spec_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
