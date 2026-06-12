# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24141700 — Packaging (segment 24).

This module provides bespoke logic for the Packaging domain, managing container
specifications, material grades, and safety verification for material handling.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24141700"
UNISPSC_TITLE = "Packaging"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24141700"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    container_type: str
    material_grade: str
    tare_weight_kg: float
    safety_compliance: bool


def configure_container(state: State) -> dict[str, Any]:
    """Determines the appropriate container type based on input item properties."""
    inp = state.get("input") or {}
    weight = inp.get("weight", 0)
    fragile = inp.get("fragile", False)

    if fragile:
        container = "reinforced_cushioned_crate"
        grade = "Industrial-A"
    elif weight > 50:
        container = "heavy_duty_pallet_box"
        grade = "Industrial-B"
    else:
        container = "standard_corrugated_carton"
        grade = "Standard-C"

    return {
        "log": [f"{UNISPSC_CODE}:configure_container"],
        "container_type": container,
        "material_grade": grade,
    }


def verify_safety_specs(state: State) -> dict[str, Any]:
    """Calculates tare weight and verifies safety compliance for the selected grade."""
    grade = state.get("material_grade", "Standard-C")

    # Logic for tare weight based on grade
    tare_weights = {
        "Industrial-A": 5.5,
        "Industrial-B": 8.2,
        "Standard-C": 1.1,
    }

    tare = tare_weights.get(grade, 1.0)
    # Assume all Industrial grades are pre-verified for safety
    is_compliant = grade.startswith("Industrial")

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_specs"],
        "tare_weight_kg": tare,
        "safety_compliance": is_compliant,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Generates the final packaging result with technical specifications."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "packaging_manifest": {
                "container": state.get("container_type"),
                "grade": state.get("material_grade"),
                "tare_kg": state.get("tare_weight_kg"),
                "certified": state.get("safety_compliance"),
            },
            "status": "sealed",
        },
    }


_g = StateGraph(State)
_g.add_node("configure_container", configure_container)
_g.add_node("verify_safety_specs", verify_safety_specs)
_g.add_node("finalize_manifest", finalize_manifest)

_g.add_edge(START, "configure_container")
_g.add_edge("configure_container", "verify_safety_specs")
_g.add_edge("verify_safety_specs", "finalize_manifest")
_g.add_edge("finalize_manifest", END)

graph = _g.compile()
