# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101734 — Carburetor diaphragms (segment 26).

Bespoke graph logic for carburetor diaphragm quality assurance and technical
validation within the power generation machinery segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101734"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101734"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Carburetor Diaphragms
    material_grade: str
    thickness_verified: bool
    vacuum_pressure_psi: float
    integrity_status: str


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the material grade and thickness specifications of the diaphragm."""
    inp = state.get("input") or {}
    material = inp.get("material", "Nitrile-Standard")
    thickness = inp.get("thickness_mm", 0.5)

    # Simple validation logic
    is_valid = 0.2 <= thickness <= 1.0
    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "material_grade": material,
        "thickness_verified": is_valid,
        "integrity_status": "PENDING"
    }


def pressure_test(state: State) -> dict[str, Any]:
    """Simulates a vacuum pressure test to ensure no leaks or deformities."""
    current_log = [f"{UNISPSC_CODE}:pressure_test"]
    if not state.get("thickness_verified"):
        return {"log": current_log + ["test_skipped_due_to_specs"], "vacuum_pressure_psi": 0.0}

    # Simulated test result
    pressure = 14.7  # standard atmospheric or specific test bench value
    return {
        "log": current_log,
        "vacuum_pressure_psi": pressure,
        "integrity_status": "TESTED_PASSED"
    }


def certify(state: State) -> dict[str, Any]:
    """Finalizes the validation and emits the certification result."""
    passed = (
        state.get("thickness_verified", False) and
        state.get("integrity_status") == "TESTED_PASSED"
    )

    return {
        "log": [f"{UNISPSC_CODE}:certify"],
        "result": {
            "code": UNISPSC_CODE,
            "title": "Carburetor Diaphragm",
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": passed,
            "metrics": {
                "material": state.get("material_grade"),
                "pressure": state.get("vacuum_pressure_psi")
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("pressure_test", pressure_test)
_g.add_node("certify", certify)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "pressure_test")
_g.add_edge("pressure_test", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
