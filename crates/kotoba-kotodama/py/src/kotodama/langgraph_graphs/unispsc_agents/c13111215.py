# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111215 — Copper (segment 13).

Bespoke graph logic for managing copper material lifecycle, purity
verification, and grading standards. This agent processes copper lot
data and categorizes it based on metallurgical specifications.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111215"
UNISPSC_TITLE = "Copper"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111215"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Copper
    purity_percent: float
    lot_identifier: str
    grade_rating: str
    assay_verified: bool


def verify_lot_spec(state: State) -> dict[str, Any]:
    """Initial validation of the copper lot and purity specs."""
    inp = state.get("input") or {}
    purity = inp.get("purity", 0.0)
    lot_id = inp.get("lot_id", "UNKNOWN-LOT")
    return {
        "log": [f"{UNISPSC_CODE}:verify_lot_spec"],
        "purity_percent": purity,
        "lot_identifier": lot_id,
        "assay_verified": purity > 99.0,
    }


def categorize_grade(state: State) -> dict[str, Any]:
    """Determines the commercial grade of the copper based on purity."""
    purity = state.get("purity_percent", 0.0)

    if purity >= 99.99:
        grade = "High Purity (Electronic)"
    elif purity >= 99.95:
        grade = "Grade A"
    elif purity >= 99.90:
        grade = "Grade 1"
    else:
        grade = "Commercial/Industrial"

    return {
        "log": [f"{UNISPSC_CODE}:categorize_grade"],
        "grade_rating": grade,
    }


def finalize_asset(state: State) -> dict[str, Any]:
    """Finalizes the state and constructs the result payload."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "lot_id": state.get("lot_identifier"),
            "grade": state.get("grade_rating"),
            "purity": state.get("purity_percent"),
            "status": "Verified" if state.get("assay_verified") else "Unverified",
            "did": UNISPSC_DID,
        },
    }


_g = StateGraph(State)
_g.add_node("verify", verify_lot_spec)
_g.add_node("grade", categorize_grade)
_g.add_node("finalize", finalize_asset)

_g.add_edge(START, "verify")
_g.add_edge("verify", "grade")
_g.add_edge("grade", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
