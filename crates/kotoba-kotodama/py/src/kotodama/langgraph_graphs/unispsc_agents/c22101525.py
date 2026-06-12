# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101525 — Fastener (segment 22).

Bespoke logic for managing fastener specifications, material verification,
and inventory tracking within the Etz Hayyim supply chain.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101525"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101525"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Fasteners
    material_grade: str
    tensile_strength_verified: bool
    thread_pitch_checked: bool
    batch_quantity: int


def inspect_hardware(state: State) -> dict[str, Any]:
    """Validates the fastener specifications and material grade from input."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "Standard")
    pitch = inp.get("thread_pitch", "M8")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_hardware"],
        "material_grade": grade,
        "thread_pitch_checked": True if pitch else False,
    }


def verify_mechanical_properties(state: State) -> dict[str, Any]:
    """Checks tensile strength requirements based on material grade."""
    grade = state.get("material_grade", "Standard")
    # High-grade fasteners require specific tensile verification logic
    strength_verified = grade in ["Grade 8", "A4-80", "10.9", "12.9"]

    return {
        "log": [f"{UNISPSC_CODE}:verify_mechanical_properties"],
        "tensile_strength_verified": strength_verified,
        "batch_quantity": state.get("input", {}).get("quantity", 0)
    }


def prepare_logistics_record(state: State) -> dict[str, Any]:
    """Finalizes the data for the logistics manifest and inventory update."""
    is_ok = state.get("thread_pitch_checked", False)

    return {
        "log": [f"{UNISPSC_CODE}:prepare_logistics_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "material": state.get("material_grade"),
                "high_strength_grade": state.get("tensile_strength_verified", False),
                "count": state.get("batch_quantity", 0)
            },
            "status": "ready_for_assembly" if is_ok else "inspection_pending",
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_hardware", inspect_hardware)
_g.add_node("verify_mechanical_properties", verify_mechanical_properties)
_g.add_node("prepare_logistics_record", prepare_logistics_record)

_g.add_edge(START, "inspect_hardware")
_g.add_edge("inspect_hardware", "verify_mechanical_properties")
_g.add_edge("verify_mechanical_properties", "prepare_logistics_record")
_g.add_edge("prepare_logistics_record", END)

graph = _g.compile()
