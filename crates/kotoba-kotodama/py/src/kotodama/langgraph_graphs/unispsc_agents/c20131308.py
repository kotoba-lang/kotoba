# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20131308 — Belt (segment 20).

Bespoke graph logic for industrial and power transmission belt specifications.
This agent handles material inspection, mechanical tension calculation,
and final specification generation for industrial belt components.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20131308"
UNISPSC_TITLE = "Belt"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20131308"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for industrial belts
    material_composition: str
    width_mm: float
    tensile_strength_rating: float
    is_fire_resistant: bool
    quality_grade: str


def inspect_composition(state: State) -> dict[str, Any]:
    """Analyzes the material properties of the belt."""
    inp = state.get("input") or {}
    material = inp.get("material", "Nitrile Rubber")
    width = float(inp.get("width", 75.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_composition"],
        "material_composition": material,
        "width_mm": width,
        "quality_grade": "Industrial-A"
    }


def compute_mechanical_specs(state: State) -> dict[str, Any]:
    """Calculates tensile strength and safety features based on dimensions."""
    width = state.get("width_mm", 0.0)
    material = state.get("material_composition", "")

    # Mock calculation logic
    multiplier = 2.5 if "Rubber" in material else 1.8
    strength = width * multiplier
    fire_safe = "Nitrile" in material or "Silicone" in material

    return {
        "log": [f"{UNISPSC_CODE}:compute_mechanical_specs"],
        "tensile_strength_rating": strength,
        "is_fire_resistant": fire_safe
    }


def finalize_belt_manifest(state: State) -> dict[str, Any]:
    """Packages the belt specifications into the final result."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_belt_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "material": state.get("material_composition"),
                "dimensions": f"{state.get('width_mm')}mm",
                "tensile_rating": f"{state.get('tensile_strength_rating')} kN",
                "fire_resistant": state.get("is_fire_resistant"),
                "grade": state.get("quality_grade")
            },
            "status": "COMPLIANT"
        }
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_composition)
_g.add_node("calculate", compute_mechanical_specs)
_g.add_node("finalize", finalize_belt_manifest)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calculate")
_g.add_edge("calculate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
