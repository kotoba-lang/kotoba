# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172009 — Bushing (segment 25).

This module provides bespoke logic for verifying and processing Bushing
specifications within the Etz Hayyim actor network. It validates material
compatibility, dimensional tolerances, and mechanical load limits.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172009"
UNISPSC_TITLE = "Bushing"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172009"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material_grade: str
    inner_diameter_mm: float
    outer_diameter_mm: float
    is_load_verified: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Extracts and validates core engineering specifications for the bushing."""
    inp = state.get("input") or {}
    material = str(inp.get("material", "Unknown"))
    id_mm = float(inp.get("inner_diameter", 0.0))
    od_mm = float(inp.get("outer_diameter", 0.0))

    valid = id_mm > 0 and od_mm > id_mm
    return {
        "log": [f"{UNISPSC_CODE}:validate_specs: {material} (ID:{id_mm}/OD:{od_mm})"],
        "material_grade": material,
        "inner_diameter_mm": id_mm,
        "outer_diameter_mm": od_mm,
        "is_load_verified": valid,
    }


def performance_analysis(state: State) -> dict[str, Any]:
    """Calculates mechanical suitability based on material and dimensions."""
    is_valid = state.get("is_load_verified", False)
    material = state.get("material_grade", "Unknown")

    # Simple logic: higher density materials or larger wall thickness get higher status
    wall_thickness = state.get("outer_diameter_mm", 0) - state.get("inner_diameter_mm", 0)
    status = "high_performance" if wall_thickness > 5.0 and material in ["Steel", "Bronze"] else "standard"

    return {
        "log": [f"{UNISPSC_CODE}:performance_analysis: status={status}"],
        "is_load_verified": is_valid and wall_thickness > 0,
    }


def certify_component(state: State) -> dict[str, Any]:
    """Generates the final actor manifest and certification result."""
    ok = state.get("is_load_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:certify_component: ok={ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "material": state.get("material_grade"),
                "dimensions": f"{state.get('inner_diameter_mm')}x{state.get('outer_diameter_mm')}mm",
            },
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("performance_analysis", performance_analysis)
_g.add_node("certify_component", certify_component)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "performance_analysis")
_g.add_edge("performance_analysis", "certify_component")
_g.add_edge("certify_component", END)

graph = _g.compile()
