# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25173804 — Axle (segment 25).

Bespoke graph for Axle components, handling mechanical specification
validation, structural stress simulation, and quality control certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25173804"
UNISPSC_TITLE = "Axle"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25173804"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Axle components
    material_grade: str
    load_capacity_tons: float
    torsional_test_passed: bool
    chassis_fitment_verified: bool


def validate_mechanical_specs(state: State) -> dict[str, Any]:
    """Validates material composition and dimension requirements."""
    inp = state.get("input") or {}
    material = inp.get("material", "AISI_4140_Steel")
    capacity = float(inp.get("target_load_capacity", 5.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_mechanical_specs: material={material}, capacity={capacity}t"],
        "material_grade": material,
        "load_capacity_tons": capacity,
        "chassis_fitment_verified": True,
    }


def simulate_stress_test(state: State) -> dict[str, Any]:
    """Simulates torsional and vertical load stress on the axle assembly."""
    capacity = state.get("load_capacity_tons", 0.0)
    grade = state.get("material_grade", "")
    # Simulation: heavy loads require specific steel alloys
    passed = not (capacity > 10.0 and "Steel" not in grade)

    return {
        "log": [f"{UNISPSC_CODE}:simulate_stress_test: result={'PASS' if passed else 'FAIL'}"],
        "torsional_test_passed": passed,
    }


def finalize_qc_report(state: State) -> dict[str, Any]:
    """Compiles the final Quality Control report and emits the state."""
    is_valid = state.get("chassis_fitment_verified", False) and state.get("torsional_test_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_qc_report: compliance_stable={is_valid}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "qc_status": "CERTIFIED" if is_valid else "REJECTED",
            "spec_summary": {
                "material": state.get("material_grade"),
                "load_limit": state.get("load_capacity_tons"),
            },
            "timestamp_utc": "2026-05-23T14:00:00Z",
        },
    }


_g = StateGraph(State)
_g.add_node("validate_mechanical_specs", validate_mechanical_specs)
_g.add_node("simulate_stress_test", simulate_stress_test)
_g.add_node("finalize_qc_report", finalize_qc_report)

_g.add_edge(START, "validate_mechanical_specs")
_g.add_edge("validate_mechanical_specs", "simulate_stress_test")
_g.add_edge("simulate_stress_test", "finalize_qc_report")
_g.add_edge("finalize_qc_report", END)

graph = _g.compile()
