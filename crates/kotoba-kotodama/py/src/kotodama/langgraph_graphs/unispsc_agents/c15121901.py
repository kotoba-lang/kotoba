# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15121901 — Steel (segment 15).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15121901"
UNISPSC_TITLE = "Steel"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15121901"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke Steel domain fields
    steel_grade: str
    heat_number: str
    mill_test_report_verified: bool
    thickness_mm: float


def validate_metallurgical_spec(state: State) -> dict[str, Any]:
    """Validates the steel grade and metallurgical requirements."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "ASTM A36")
    thickness = float(inp.get("thickness", 5.0))

    # Simple validation logic for steel standards
    is_standard = any(prefix in grade.upper() for prefix in ["ASTM", "AISI", "SAE", "DIN"])

    return {
        "log": [f"{UNISPSC_CODE}:validate_metallurgical_spec"],
        "steel_grade": grade,
        "thickness_mm": thickness,
        "mill_test_report_verified": is_standard,
    }


def assign_inventory_heat(state: State) -> dict[str, Any]:
    """Simulates the allocation of a specific heat/batch number from inventory."""
    grade = state.get("steel_grade", "GENERIC")
    verified = state.get("mill_test_report_verified", False)

    # Generate a dummy heat number if verified, otherwise mark as pending
    heat_id = f"HEAT-{grade.replace(' ', '-')}-2026-05" if verified else "PENDING_CERT"

    return {
        "log": [f"{UNISPSC_CODE}:assign_inventory_heat"],
        "heat_number": heat_id,
    }


def finalize_procurement_record(state: State) -> dict[str, Any]:
    """Finalizes the steel procurement process and emits the result."""
    verified = state.get("mill_test_report_verified", False)
    heat = state.get("heat_number", "")

    ok = verified and "PENDING" not in heat

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "summary": {
                "grade": state.get("steel_grade"),
                "heat_number": heat,
                "thickness": state.get("thickness_mm"),
                "verified": verified,
            },
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_metallurgical_spec)
_g.add_node("assign", assign_inventory_heat)
_g.add_node("finalize", finalize_procurement_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assign")
_g.add_edge("assign", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
