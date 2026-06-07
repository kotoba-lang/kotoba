# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11111701 — Coal Procurement (segment 11).

Bespoke LangGraph logic for managing the procurement lifecycle of coal,
focusing on quality specification validation and contract authorization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11111701"
UNISPSC_TITLE = "Coal Procurement"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11111701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Coal Procurement
    calorific_value_kcal: int
    sulfur_content_percent: float
    ash_content_percent: float
    is_compliant: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Inspects the incoming coal batch specifications for baseline compliance."""
    inp = state.get("input") or {}
    cal = inp.get("calorific_value", 0)
    sulfur = inp.get("sulfur_content", 100.0)
    ash = inp.get("ash_content", 100.0)

    # Basic compliance: High energy, low impurities
    compliant = cal > 5000 and sulfur < 1.0 and ash < 15.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "calorific_value_kcal": cal,
        "sulfur_content_percent": sulfur,
        "ash_content_percent": ash,
        "is_compliant": compliant,
    }


def assess_grade(state: State) -> dict[str, Any]:
    """Categorizes the coal based on thermal energy and impurity levels."""
    cal = state.get("calorific_value_kcal", 0)
    grade = "Standard"
    if cal > 7000:
        grade = "Premium Anthracite"
    elif cal > 6000:
        grade = "High-Volatile Bituminous"

    return {
        "log": [f"{UNISPSC_CODE}:assess_grade (Grade: {grade})"],
        "result": {"coal_grade": grade}
    }


def authorize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement decision based on compliance and grade assessment."""
    is_compliant = state.get("is_compliant", False)
    grade_info = state.get("result", {}).get("coal_grade", "Unknown")

    status = "REJECTED" if not is_compliant else "APPROVED"

    return {
        "log": [f"{UNISPSC_CODE}:authorize_procurement -> {status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_status": status,
            "grade_assigned": grade_info,
            "ok": is_compliant,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("assess_grade", assess_grade)
_g.add_node("authorize_procurement", authorize_procurement)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "assess_grade")
_g.add_edge("assess_grade", "authorize_procurement")
_g.add_edge("authorize_procurement", END)

graph = _g.compile()
