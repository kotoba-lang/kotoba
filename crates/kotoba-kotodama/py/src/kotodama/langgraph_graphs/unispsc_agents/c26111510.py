# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111510 — Shaft (segment 26).

Bespoke logic for power transmission shafts. This agent manages technical
specifications, material selection, and structural integrity verification for
rotational components within the Power Generation and Distribution segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111510"
UNISPSC_TITLE = "Shaft"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111510"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Shaft components
    material_grade: str
    diameter_mm: float
    tensile_strength_mpa: float
    load_capacity_nm: float
    is_structurally_sound: bool


def ingest_design_params(state: State) -> dict[str, Any]:
    """Ingests and sanitizes shaft geometry and material requirements."""
    inp = state.get("input") or {}
    material = str(inp.get("material", "AISI 1045"))
    diameter = float(inp.get("diameter", 25.0))

    return {
        "log": [f"{UNISPSC_CODE}:ingest_design_params"],
        "material_grade": material,
        "diameter_mm": diameter
    }


def evaluate_structural_integrity(state: State) -> dict[str, Any]:
    """Performs mechanical analysis based on shaft dimensions and material properties."""
    material = state.get("material_grade", "AISI 1045")
    diameter = state.get("diameter_mm", 0.0)

    # Material property mapping
    properties = {
        "AISI 1045": {"tensile": 570.0, "yield": 310.0},
        "AISI 4140": {"tensile": 655.0, "yield": 415.0},
        "Stainless 304": {"tensile": 515.0, "yield": 205.0}
    }

    spec = properties.get(material, properties["AISI 1045"])

    # Mock calculation for torsional capacity based on diameter cubed
    # T = (pi * d^3 * shear_stress) / 16
    capacity = (3.14159 * (diameter ** 3) * (spec["yield"] * 0.5)) / 16.0

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_structural_integrity"],
        "tensile_strength_mpa": spec["tensile"],
        "load_capacity_nm": round(capacity, 2),
        "is_structurally_sound": diameter >= 12.0
    }


def finalize_specification(state: State) -> dict[str, Any]:
    """Generates the final engineering record for procurement or manufacturing."""
    sound = state.get("is_structurally_sound", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "disposition": "APPROVED" if sound else "REVISION_REQUIRED",
            "specs": {
                "material": state.get("material_grade"),
                "diameter": state.get("diameter_mm"),
                "tensile_strength": state.get("tensile_strength_mpa"),
                "max_torque": state.get("load_capacity_nm")
            },
            "verified": sound
        }
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_design_params)
_g.add_node("evaluate", evaluate_structural_integrity)
_g.add_node("finalize", finalize_specification)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "evaluate")
_g.add_edge("evaluate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
