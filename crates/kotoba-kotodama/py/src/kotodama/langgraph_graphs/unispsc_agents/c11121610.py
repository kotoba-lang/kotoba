# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11121610 — Metal Procurement (segment 11).

Bespoke graph implementing metallurgy-specific procurement logic including
request initialization, metallurgical specification verification, and
procurement manifest generation.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11121610"
UNISPSC_TITLE = "Metal Procurement"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11121610"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific procurement state
    metal_category: str
    purity_grade: float
    order_quantity_mt: float
    spec_verification_status: str


def initialize_request(state: State) -> dict[str, Any]:
    """Parses the input procurement request into domain state."""
    inp = state.get("input") or {}
    category = str(inp.get("category", "Standard Alloy"))
    quantity = float(inp.get("quantity", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:initialize_request"],
        "metal_category": category,
        "order_quantity_mt": quantity,
    }


def verify_specifications(state: State) -> dict[str, Any]:
    """Simulates metallurgical analysis of the requested procurement order."""
    quantity = state.get("order_quantity_mt", 0.0)
    # Simulation: large orders trigger high-purity industrial grade requirements
    grade = 0.9995 if quantity > 500.0 else 0.9850
    status = "VERIFIED" if quantity > 0 else "INVALID_QUANTITY"

    return {
        "log": [f"{UNISPSC_CODE}:verify_specifications"],
        "purity_grade": grade,
        "spec_verification_status": status,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Generates the final procurement manifest result."""
    status = state.get("spec_verification_status")
    is_ok = status == "VERIFIED"

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "did": UNISPSC_DID,
        "ok": is_ok,
        "manifest": {
            "metal": state.get("metal_category"),
            "grade": state.get("purity_grade"),
            "volume": state.get("order_quantity_mt"),
            "verification": status
        }
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": res,
    }


_g = StateGraph(State)
_g.add_node("initialize_request", initialize_request)
_g.add_node("verify_specifications", verify_specifications)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "initialize_request")
_g.add_edge("initialize_request", "verify_specifications")
_g.add_edge("verify_specifications", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
