# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111806 — Paper Procure (segment 14).

Bespoke graph logic for paper procurement, handling specifications,
supplier verification, and order finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111806"
UNISPSC_TITLE = "Paper Procure"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111806"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Paper Procure
    specs_validated: bool
    supplier_id: str
    quality_grade: str
    procurement_confirmed: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates paper specifications (gsm, dimensions, finish)."""
    inp = state.get("input") or {}
    # Simulate checking for required paper attributes
    has_gsm = "gsm" in inp
    has_dimensions = "dimensions" in inp

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "specs_validated": has_gsm and has_dimensions,
        "quality_grade": inp.get("grade", "standard")
    }


def verify_supplier(state: State) -> dict[str, Any]:
    """Verifies supplier availability and reliability for paper stock."""
    if not state.get("specs_validated"):
        return {"log": [f"{UNISPSC_CODE}:verify_supplier_skipped"]}

    # Simulate selecting a supplier based on grade
    grade = state.get("quality_grade")
    sid = "SUP-PAPER-001" if grade == "premium" else "SUP-PAPER-GEN"

    return {
        "log": [f"{UNISPSC_CODE}:verify_supplier"],
        "supplier_id": sid
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the paper procurement order."""
    success = state.get("specs_validated", False) and bool(state.get("supplier_id"))

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "procurement_confirmed": success,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "order_status": "confirmed" if success else "pending",
            "supplier": state.get("supplier_id"),
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("verify", verify_supplier)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
