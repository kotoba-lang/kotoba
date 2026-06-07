# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20142000 — Aerospace Valve (segment 20).

Bespoke graph logic for Aerospace Valve manufacturing and certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20142000"
UNISPSC_TITLE = "Aerospace Valve"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20142000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields
    pressure_rating_psi: int
    material_spec: str
    pressure_test_passed: bool
    safety_certified: bool


def validate_specs(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    pressure = inp.get("pressure_psi", 3000)
    material = inp.get("material", "Titanium-Alloy-6Al-4V")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs: {material} at {pressure} PSI"],
        "pressure_rating_psi": pressure,
        "material_spec": material,
    }


def pressure_test(state: State) -> dict[str, Any]:
    # Simulate pressure testing for aerospace standards
    rating = state.get("pressure_rating_psi", 0)
    # Aerospace valves typically handle high pressure; validation check within tolerances
    passed = rating > 0 and rating <= 15000

    return {
        "log": [f"{UNISPSC_CODE}:pressure_test: {'PASSED' if passed else 'FAILED'}"],
        "pressure_test_passed": passed,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    test_passed = state.get("pressure_test_passed", False)
    certified = test_passed and state.get("material_spec") is not None

    cert_id = f"AS-VALVE-{UNISPSC_CODE}-777" if certified else "N/A"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification: {cert_id}"],
        "safety_certified": certified,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification_id": cert_id,
            "status": "APPROVED" if certified else "REJECTED",
            "ok": certified,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("pressure_test", pressure_test)
_g.add_node("finalize_certification", finalize_certification)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "pressure_test")
_g.add_edge("pressure_test", "finalize_certification")
_g.add_edge("finalize_certification", END)

graph = _g.compile()
