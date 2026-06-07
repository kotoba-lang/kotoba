# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20101617 — Oil and Gas Well Casing (segment 20).

Bespoke graph logic for verifying casing specifications and compliance
with industry standards like API 5CT for oil and gas well construction.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20101617"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20101617"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    casing_grade: str
    nominal_weight: float
    inspection_passed: bool
    compliance_status: str


def inspect_specifications(state: State) -> dict[str, Any]:
    """Validate casing dimensions and grade against design requirements."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "J-55")
    weight = float(inp.get("weight", 0.0))

    # Basic validation: ensure grade is provided and weight is positive
    passed = weight > 0 and len(grade) >= 2

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "casing_grade": grade,
        "nominal_weight": weight,
        "inspection_passed": passed,
    }


def verify_api_compliance(state: State) -> dict[str, Any]:
    """Check if the material grade meets API 5CT standards."""
    grade = state.get("casing_grade", "")
    # Standard API 5CT casing grades
    api_grades = {"H-40", "J-55", "K-55", "N-80", "L-80", "C-90", "T-95", "P-110", "Q-125"}

    status = "compliant" if grade in api_grades else "non-compliant"

    return {
        "log": [f"{UNISPSC_CODE}:verify_api_compliance"],
        "compliance_status": status,
    }


def generate_certificate(state: State) -> dict[str, Any]:
    """Finalize the verification result and emit certification metadata."""
    success = state.get("inspection_passed") and state.get("compliance_status") == "compliant"

    return {
        "log": [f"{UNISPSC_CODE}:generate_certificate"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": success,
            "details": {
                "grade": state.get("casing_grade"),
                "weight": state.get("nominal_weight"),
                "status": state.get("compliance_status"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_specifications", inspect_specifications)
_g.add_node("verify_api_compliance", verify_api_compliance)
_g.add_node("generate_certificate", generate_certificate)

_g.add_edge(START, "inspect_specifications")
_g.add_edge("inspect_specifications", "verify_api_compliance")
_g.add_edge("verify_api_compliance", "generate_certificate")
_g.add_edge("generate_certificate", END)

graph = _g.compile()
