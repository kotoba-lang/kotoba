# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153404 — Welding (segment 23).

Bespoke graph logic for welding operations, including parameter validation,
weld execution simulation, and post-weld quality inspection.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153404"
UNISPSC_TITLE = "Welding"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153404"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Welding
    material_grade: str
    weld_type: str
    heat_input_kj_mm: float
    inspection_passed: bool


def validate_welding_params(state: State) -> dict[str, Any]:
    """Validates the material grade and welding method from input."""
    inp = state.get("input") or {}
    material = inp.get("material", "ASTM A36")
    method = inp.get("method", "GMAW")

    return {
        "log": [f"{UNISPSC_CODE}:validate_welding_params -> {material}/{method}"],
        "material_grade": material,
        "weld_type": method,
    }


def execute_weld_sequence(state: State) -> dict[str, Any]:
    """Simulates the welding process and calculates theoretical heat input."""
    # Standard heat input values (kJ/mm) based on common welding methods
    method = state.get("weld_type", "GMAW")
    heat_map = {"GMAW": 0.85, "GTAW": 1.25, "SMAW": 1.60}
    calculated_heat = heat_map.get(method, 1.0)

    return {
        "log": [f"{UNISPSC_CODE}:execute_weld_sequence -> heat_input: {calculated_heat}"],
        "heat_input_kj_mm": calculated_heat,
    }


def perform_post_weld_inspection(state: State) -> dict[str, Any]:
    """Simulates a non-destructive testing (NDT) inspection of the joint."""
    heat = state.get("heat_input_kj_mm", 0.0)
    # Logic: if heat input is within metallurgical safety bounds, inspection passes
    passed = 0.5 <= heat <= 2.0

    return {
        "log": [f"{UNISPSC_CODE}:perform_post_weld_inspection -> passed: {passed}"],
        "inspection_passed": passed,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "COMPLETED" if passed else "FAILED_INSPECTION",
            "metrics": {
                "material": state.get("material_grade"),
                "method": state.get("weld_type"),
                "heat_input_kj_mm": heat
            },
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_welding_params)
_g.add_node("weld", execute_weld_sequence)
_g.add_node("inspect", perform_post_weld_inspection)

_g.add_edge(START, "validate")
_g.add_edge("validate", "weld")
_g.add_edge("weld", "inspect")
_g.add_edge("inspect", END)

graph = _g.compile()
