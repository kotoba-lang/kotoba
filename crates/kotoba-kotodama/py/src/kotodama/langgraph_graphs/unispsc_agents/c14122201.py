# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14122201 — Rubber Procure (segment 14).

Bespoke graph logic for rubber material procurement. This agent handles
source validation, quality certification verification, and procurement
finalization for rubber batch records.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14122201"
UNISPSC_TITLE = "Rubber Procure"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14122201"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    rubber_grade: str
    is_certified: bool
    batch_volume: float
    procurement_status: str


def validate_source(state: State) -> dict[str, Any]:
    """Extract and validate the rubber source and grade from input."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "Standard Industrial")
    volume = float(inp.get("volume", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_source -> {grade}"],
        "rubber_grade": grade,
        "batch_volume": volume,
    }


def verify_quality(state: State) -> dict[str, Any]:
    """Perform a mock certification check on the rubber batch."""
    grade = state.get("rubber_grade", "")
    # In this mock logic, "Premium" or "Medical" grades require explicit flags,
    # while "Standard" is auto-verified for this example.
    certified = "Standard" in grade or state.get("input", {}).get("certified", False)

    return {
        "log": [f"{UNISPSC_CODE}:verify_quality -> certified: {certified}"],
        "is_certified": certified,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalize the procurement record based on volume and certification."""
    volume = state.get("batch_volume", 0.0)
    certified = state.get("is_certified", False)

    success = volume > 0 and certified
    status = "PROCESSED" if success else "FLAGGED_FOR_REVIEW"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement -> {status}"],
        "procurement_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": status,
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_source", validate_source)
_g.add_node("verify_quality", verify_quality)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_source")
_g.add_edge("validate_source", "verify_quality")
_g.add_edge("verify_quality", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
