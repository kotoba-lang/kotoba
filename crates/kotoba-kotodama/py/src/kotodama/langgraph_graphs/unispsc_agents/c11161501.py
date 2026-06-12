# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11161501 — Lubricant (segment 11).

Bespoke graph logic for evaluating lubricant specifications, verifying
compliance with industrial standards, and certifying product data.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11161501"
UNISPSC_TITLE = "Lubricant"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11161501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Lubricants
    viscosity_grade: str
    base_oil_type: str
    flash_point_celsius: float
    specification_verified: bool
    performance_category: str


def evaluate_properties(state: State) -> dict[str, Any]:
    """Analyze input data for lubricant physical properties."""
    inp = state.get("input") or {}
    v_grade = inp.get("viscosity", "ISO VG 46")
    oil_type = inp.get("base_oil", "Mineral")
    flash = float(inp.get("flash_point", 220.0))

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_properties"],
        "viscosity_grade": v_grade,
        "base_oil_type": oil_type,
        "flash_point_celsius": flash,
    }


def validate_standard(state: State) -> dict[str, Any]:
    """Verify the lubricant against industrial performance standards."""
    v_grade = state.get("viscosity_grade", "")
    flash = state.get("flash_point_celsius", 0.0)

    # Simple logic: higher flash point and standard viscosity grades pass
    is_valid = flash > 150.0 and v_grade.startswith("ISO")
    perf = "Premium" if flash > 240.0 else "Standard"

    return {
        "log": [f"{UNISPSC_CODE}:validate_standard"],
        "specification_verified": is_valid,
        "performance_category": perf,
    }


def certify_lubricant(state: State) -> dict[str, Any]:
    """Generate the final result and certification status."""
    verified = state.get("specification_verified", False)
    perf = state.get("performance_category", "Unknown")

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "certified": verified,
        "grade": state.get("viscosity_grade"),
        "performance": perf,
        "ok": verified,
    }

    return {
        "log": [f"{UNISPSC_CODE}:certify_lubricant"],
        "result": res,
    }


_g = StateGraph(State)

_g.add_node("evaluate", evaluate_properties)
_g.add_node("validate", validate_standard)
_g.add_node("certify", certify_lubricant)

_g.add_edge(START, "evaluate")
_g.add_edge("evaluate", "validate")
_g.add_edge("validate", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
