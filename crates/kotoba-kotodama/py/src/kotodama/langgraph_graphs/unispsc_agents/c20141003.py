# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20141003 — Bearing (segment 20).

Bespoke logic for mechanical bearing specification validation and
compatibility analysis. This agent evaluates physical dimensions,
load requirements, and environmental suitability for industrial bearings.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141003"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141003"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Bearing
    bore_diameter_mm: float
    static_load_rating_kn: float
    lubrication_method: str
    material_grade: str
    safety_check_passed: bool


def validate_spec(state: State) -> dict[str, Any]:
    """Validates basic physical constraints for the bearing specification."""
    inp = state.get("input") or {}
    bore = float(inp.get("bore", 0.0))
    load = float(inp.get("load_kn", 0.0))

    # Validation logic for standard industrial ranges
    valid = (1.0 <= bore <= 500.0) and (load >= 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_spec"],
        "bore_diameter_mm": bore,
        "static_load_rating_kn": load,
        "safety_check_passed": valid
    }


def assess_environment(state: State) -> dict[str, Any]:
    """Determines appropriate material and lubrication based on operating temperature."""
    inp = state.get("input") or {}
    temp_c = float(inp.get("operating_temp_c", 25.0))

    # Material and lubrication selection logic
    if temp_c > 120:
        lube = "high_temp_synthetic_oil"
        material = "m50_steel"
    else:
        lube = "standard_lithium_grease"
        material = "aisi_52100_chrome_steel"

    return {
        "log": [f"{UNISPSC_CODE}:assess_environment"],
        "lubrication_method": lube,
        "material_grade": material
    }


def generate_report(state: State) -> dict[str, Any]:
    """Finalizes the bearing selection report and sets the actor result."""
    passed = state.get("safety_check_passed", False)
    bore = state.get("bore_diameter_mm", 0.0)
    lube = state.get("lubrication_method", "none")
    grade = state.get("material_grade", "unknown")

    status = "verified" if passed else "insufficient_data"

    return {
        "log": [f"{UNISPSC_CODE}:generate_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": status,
            "metadata": {
                "bore_size": f"{bore}mm",
                "lubricant": lube,
                "material": grade,
                "safety_rating": "nominal" if passed else "fail"
            },
            "ok": passed
        }
    }


_g = StateGraph(State)
_g.add_node("validate_spec", validate_spec)
_g.add_node("assess_environment", assess_environment)
_g.add_node("generate_report", generate_report)

_g.add_edge(START, "validate_spec")
_g.add_edge("validate_spec", "assess_environment")
_g.add_edge("assess_environment", "generate_report")
_g.add_edge("generate_report", END)

graph = _g.compile()
