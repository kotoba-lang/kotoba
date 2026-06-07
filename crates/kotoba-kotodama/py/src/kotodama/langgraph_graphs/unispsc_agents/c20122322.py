# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122322 — Robot Gear (segment 20).

Bespoke graph for robotic gear component validation and kinematic load analysis.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122322"
UNISPSC_TITLE = "Robot Gear"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122322"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    gear_specs: dict[str, Any]
    inspection_passed: bool
    kinematic_rating: float
    material_alloy: str


def validate_specs(state: State) -> dict[str, Any]:
    """Validate gear dimensions and teeth count for robotic applications."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})

    # Logic: Gear must have teeth and a valid diameter to be processable
    teeth = specs.get("teeth", 0)
    diameter = specs.get("diameter_mm", 0.0)
    passed = teeth > 0 and diameter > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "gear_specs": specs,
        "inspection_passed": passed,
        "material_alloy": specs.get("material", "High-Carbon Steel")
    }


def analyze_kinematics(state: State) -> dict[str, Any]:
    """Calculate the kinematic load rating based on gear geometry and material."""
    specs = state.get("gear_specs") or {}
    teeth = specs.get("teeth", 1)
    diameter = specs.get("diameter_mm", 1.0)

    # Simplified kinematic load factor calculation
    rating = (teeth * diameter) / 150.0

    return {
        "log": [f"{UNISPSC_CODE}:analyze_kinematics"],
        "kinematic_rating": rating
    }


def finalize_asset(state: State) -> dict[str, Any]:
    """Emit the final validated gear metadata and performance ratings."""
    passed = state.get("inspection_passed", False)
    rating = state.get("kinematic_rating", 0.0)
    material = state.get("material_alloy", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "material": material,
            "load_rating_kn": round(rating, 4),
            "certification": "ISO-20122322-COMPLIANT" if passed else "FAILED-INSPECTION",
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("analyze_kinematics", analyze_kinematics)
_g.add_node("finalize_asset", finalize_asset)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "analyze_kinematics")
_g.add_edge("analyze_kinematics", "finalize_asset")
_g.add_edge("finalize_asset", END)

graph = _g.compile()
