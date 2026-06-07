# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24141709 — Capsule (segment 24).

This bespoke agent implements a domain-specific StateGraph for industrial
capsule containers, handling specification validation, structural integrity
verification, and certification of the unit for hazardous or sensitive storage.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24141709"
UNISPSC_TITLE = "Capsule"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24141709"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Industrial Capsule
    material_grade: str
    pressure_limit_psi: float
    is_pressure_tested: bool
    seal_type: str
    certification_status: str


def validate_specification(state: State) -> dict[str, Any]:
    """Validates the input parameters for the industrial capsule unit."""
    inp = state.get("input") or {}
    material = inp.get("material", "Carbon Steel")
    limit = float(inp.get("max_pressure", 2500.0))
    seal = inp.get("seal", "O-Ring Type A")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "material_grade": material,
        "pressure_limit_psi": limit,
        "seal_type": seal,
    }


def verify_integrity(state: State) -> dict[str, Any]:
    """Simulates a structural and pressure integrity check on the capsule."""
    limit = state.get("pressure_limit_psi", 0.0)
    # Simulation logic: higher pressure ratings require stricter validation
    tested = limit > 0 and limit < 10000.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_integrity"],
        "is_pressure_tested": tested,
    }


def issue_certification(state: State) -> dict[str, Any]:
    """Generates the final certification and result for the actor."""
    passed = state.get("is_pressure_tested", False)
    status = "CERTIFIED" if passed else "FAILED_INSPECTION"

    return {
        "log": [f"{UNISPSC_CODE}:issue_certification"],
        "certification_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "material": state.get("material_grade"),
            "status": status,
            "ok": passed,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specification)
_g.add_node("verify", verify_integrity)
_g.add_node("certify", issue_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
