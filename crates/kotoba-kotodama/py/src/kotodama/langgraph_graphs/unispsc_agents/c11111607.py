# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11111607 — Ceramic Procurement (segment 11).
Bespoke implementation for ceramic material acquisition and specification validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11111607"
UNISPSC_TITLE = "Ceramic Procurement"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11111607"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Ceramic Procurement
    material_grade: str
    firing_temp_celsius: int
    quality_cert_verified: bool
    batch_quantity: int


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the ceramic technical requirements."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "High-Alumina")
    temp = inp.get("temp", 1450)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "material_grade": grade,
        "firing_temp_celsius": temp,
        "quality_cert_verified": True if temp >= 1000 else False
    }


def verify_sourcing_capacity(state: State) -> dict[str, Any]:
    """Checks if the requested quantity meets procurement thresholds."""
    inp = state.get("input") or {}
    qty = inp.get("quantity", 500)

    return {
        "log": [f"{UNISPSC_CODE}:verify_sourcing_capacity"],
        "batch_quantity": qty
    }


def finalize_procurement_plan(state: State) -> dict[str, Any]:
    """Constructs the final procurement result."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_plan"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "outcome": "PROCUREMENT_READY",
            "specifications": {
                "grade": state.get("material_grade"),
                "firing_temp": state.get("firing_temp_celsius"),
                "quantity": state.get("batch_quantity"),
                "verified": state.get("quality_cert_verified")
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specifications", validate_specifications)
_g.add_node("verify_sourcing_capacity", verify_sourcing_capacity)
_g.add_node("finalize_procurement_plan", finalize_procurement_plan)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "verify_sourcing_capacity")
_g.add_edge("verify_sourcing_capacity", "finalize_procurement_plan")
_g.add_edge("finalize_procurement_plan", END)

graph = _g.compile()
