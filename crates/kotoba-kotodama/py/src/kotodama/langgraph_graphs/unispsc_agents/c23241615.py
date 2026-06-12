# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23241615 — Tap Procurement (segment 23).

Bespoke logic for procuring industrial taps, ensuring compliance with thread
standards and material specifications for manufacturing workflows.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23241615"
UNISPSC_TITLE = "Tap Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23241615"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    thread_standard: str
    material_grade: str
    procurement_status: str
    order_id: str


def validate_requirements(state: State) -> dict[str, Any]:
    """Validates the input for required tap specifications."""
    inp = state.get("input") or {}
    standard = inp.get("thread_standard", "NPT")
    material = inp.get("material_grade", "HSS")

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "thread_standard": standard,
        "material_grade": material,
        "procurement_status": "validated"
    }


def source_supplier(state: State) -> dict[str, Any]:
    """Identifies a supplier capable of providing the specified tap."""
    standard = state.get("thread_standard") or "NPT"
    material = state.get("material_grade") or "HSS"

    # Logic to simulate supplier matching based on tool specifications
    supplier_tag = f"SUP-TAP-{standard}-{material[:3].upper()}"

    return {
        "log": [f"{UNISPSC_CODE}:source_supplier ({supplier_tag})"],
        "order_id": f"ORD-{UNISPSC_CODE}-7782",
        "procurement_status": "sourced"
    }


def authorize_and_emit(state: State) -> dict[str, Any]:
    """Finalizes the procurement record and emits the result."""
    return {
        "log": [f"{UNISPSC_CODE}:authorize_and_emit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "authorized",
            "order_id": state.get("order_id"),
            "did": UNISPSC_DID,
            "spec": {
                "standard": state.get("thread_standard"),
                "material": state.get("material_grade")
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requirements)
_g.add_node("source", source_supplier)
_g.add_node("emit", authorize_and_emit)

_g.add_edge(START, "validate")
_g.add_edge("validate", "source")
_g.add_edge("source", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
