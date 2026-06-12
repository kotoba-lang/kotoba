# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20141601 — Bushing (segment 20).
Bespoke logic for industrial bushing validation, material assessment, and load capacity calculation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141601"
UNISPSC_TITLE = "Bushing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Bushing
    material_grade: str
    inner_diameter_mm: float
    outer_diameter_mm: float
    rated_load_kn: float
    inspection_passed: bool


def validate_mechanical_specs(state: State) -> dict[str, Any]:
    """Validates physical dimensions and ensures structural integrity of the bushing spec."""
    inp = state.get("input") or {}
    id_mm = float(inp.get("inner_diameter_mm", 0.0))
    od_mm = float(inp.get("outer_diameter_mm", 0.0))

    # Basic geometric validation
    valid = id_mm > 0 and od_mm > (id_mm + 0.5)  # Minimum 0.25mm wall thickness

    return {
        "log": [f"{UNISPSC_CODE}:validate_mechanical_specs: id={id_mm}, od={od_mm}, valid={valid}"],
        "inner_diameter_mm": id_mm,
        "outer_diameter_mm": od_mm,
        "inspection_passed": valid,
    }


def determine_load_capacity(state: State) -> dict[str, Any]:
    """Calculates the maximum rated load based on wall thickness and material properties."""
    inp = state.get("input") or {}
    material = inp.get("material_grade", "Bronze-C932")

    # Material-specific strength factors
    strength_factors = {
        "Bronze-C932": 24.0,
        "Steel-1018": 45.0,
        "Nylon-66": 8.5,
        "PTFE": 3.2
    }
    factor = strength_factors.get(material, 15.0)

    id_mm = state.get("inner_diameter_mm", 0.0)
    od_mm = state.get("outer_diameter_mm", 0.0)
    wall_thickness = (od_mm - id_mm) / 2.0

    # Simple engineering approximation: load capacity scales with wall thickness and factor
    load = wall_thickness * factor if state.get("inspection_passed") else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:determine_load_capacity: material={material}, capacity={load:.2f}kN"],
        "material_grade": material,
        "rated_load_kn": round(load, 3),
    }


def emit_certification(state: State) -> dict[str, Any]:
    """Finalizes the bushing record with full technical specifications."""
    passed = state.get("inspection_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:emit_certification: status={'APPROVED' if passed else 'FAILED'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification": "ISO-9001-BUSHING" if passed else "NONE",
            "spec_summary": {
                "material": state.get("material_grade"),
                "id": f"{state.get('inner_diameter_mm')}mm",
                "od": f"{state.get('outer_diameter_mm')}mm",
                "max_static_load": f"{state.get('rated_load_kn')}kN"
            },
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_mechanical_specs)
_g.add_node("calculate", determine_load_capacity)
_g.add_node("certify", emit_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
