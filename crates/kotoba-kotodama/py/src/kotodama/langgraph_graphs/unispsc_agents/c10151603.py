# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151603 — Grain Procurement.

Bespoke logic for managing the procurement of grain, including contract
verification, quality inspection (moisture/grade), and final settlement.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151603"
UNISPSC_TITLE = "Grain Procurement"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151603"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Grain Procurement
    crop_type: str
    moisture_content: float
    quality_grade: str
    contract_id: str
    inspection_passed: bool


def verify_contract(state: State) -> dict[str, Any]:
    """Validates the procurement contract and crop specifications."""
    inp = state.get("input") or {}
    cid = inp.get("contract_id", "PENDING")
    crop = inp.get("crop", "Corn")

    return {
        "log": [f"{UNISPSC_CODE}:verify_contract:{cid}"],
        "contract_id": cid,
        "crop_type": crop,
    }


def inspect_quality(state: State) -> dict[str, Any]:
    """Performs moisture testing and grain grading."""
    inp = state.get("input") or {}
    # Standard moisture for storage is usually < 14.5%
    moisture = float(inp.get("moisture", 13.8))

    # Simple grading logic
    if moisture < 14.0:
        grade = "US No. 1"
        passed = True
    elif moisture < 15.5:
        grade = "US No. 2"
        passed = True
    else:
        grade = "Sample Grade (High Moisture)"
        passed = False

    return {
        "log": [f"{UNISPSC_CODE}:inspect_quality:grade={grade}"],
        "moisture_content": moisture,
        "quality_grade": grade,
        "inspection_passed": passed,
    }


def settle_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement transaction and records the result."""
    passed = state.get("inspection_passed", False)
    crop = state.get("crop_type", "Unknown")
    grade = state.get("quality_grade", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:settle_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "Settled" if passed else "Rejected",
            "crop": crop,
            "grade": grade,
            "ok": passed,
        },
    }


_g = StateGraph(State)

_g.add_node("verify_contract", verify_contract)
_g.add_node("inspect_quality", inspect_quality)
_g.add_node("settle_procurement", settle_procurement)

_g.add_edge(START, "verify_contract")
_g.add_edge("verify_contract", "inspect_quality")
_g.add_edge("inspect_quality", "settle_procurement")
_g.add_edge("settle_procurement", END)

graph = _g.compile()
