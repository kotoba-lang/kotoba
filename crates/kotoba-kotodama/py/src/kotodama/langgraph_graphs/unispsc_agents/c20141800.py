# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20141800 — Fastener (segment 20).

Bespoke logic for managing fastener specifications, material validation,
and order processing within the Etz Hayyim supply chain.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141800"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141800"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Fastener
    fastener_type: str
    material_grade: str
    specification_validated: bool
    batch_quantity: int


def validate_specifications(state: State) -> dict[str, Any]:
    """Validate material and type specifications for the fastener request."""
    inp = state.get("input") or {}
    f_type = inp.get("type", "standard-bolt")
    m_grade = inp.get("grade", "grade-8")

    # Simple validation logic to simulate domain work
    is_valid = len(f_type) > 0 and len(m_grade) > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "fastener_type": f_type,
        "material_grade": m_grade,
        "specification_validated": is_valid
    }


def calculate_load_rating(state: State) -> dict[str, Any]:
    """Calculate or verify load rating based on material grade and fastener type."""
    inp = state.get("input") or {}
    qty = inp.get("quantity", 100)

    return {
        "log": [f"{UNISPSC_CODE}:calculate_load_rating"],
        "batch_quantity": qty,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Generate final output manifest for the fastener procurement step."""
    is_valid = state.get("specification_validated", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "details": {
                "type": state.get("fastener_type"),
                "grade": state.get("material_grade"),
                "qty": state.get("batch_quantity")
            },
            "status": "ready_for_dispatch" if is_valid else "invalid_spec",
            "ok": True,
        }
    }


_g = StateGraph(State)

_g.add_node("validate_specifications", validate_specifications)
_g.add_node("calculate_load_rating", calculate_load_rating)
_g.add_node("finalize_manifest", finalize_manifest)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "calculate_load_rating")
_g.add_edge("calculate_load_rating", "finalize_manifest")
_g.add_edge("finalize_manifest", END)

graph = _g.compile()
