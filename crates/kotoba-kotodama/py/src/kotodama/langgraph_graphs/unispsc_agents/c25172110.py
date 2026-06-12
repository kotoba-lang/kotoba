# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172110 — Horn Procurement (segment 25).
Bespoke logic for vehicle horn component acquisition and validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172110"
UNISPSC_TITLE = "Horn Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172110"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields
    horn_type: str  # e.g., Electric, Air, Diaphragm
    voltage_rating: int  # 12V, 24V
    decibel_level: int
    compliance_check: bool
    procurement_status: str


def validate_specification(state: State) -> dict[str, Any]:
    """Validates the horn specifications against vehicle requirements."""
    inp = state.get("input") or {}
    h_type = inp.get("horn_type", "Standard Electric")
    voltage = inp.get("voltage", 12)
    db = inp.get("decibel_level", 110)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "horn_type": h_type,
        "voltage_rating": voltage,
        "decibel_level": db,
        "compliance_check": 85 <= db <= 125,
    }


def verify_regulatory_compliance(state: State) -> dict[str, Any]:
    """Ensures the horn meets safety and noise pollution regulations."""
    is_compliant = state.get("compliance_check", False)
    status = "Approved" if is_compliant else "Rejected - Noise Level Out of Bounds"

    return {
        "log": [f"{UNISPSC_CODE}:verify_regulatory_compliance"],
        "procurement_status": status,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement record for the specified horn component."""
    status = state.get("procurement_status", "Pending")
    h_type = state.get("horn_type", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "component": h_type,
            "status": status,
            "ok": status == "Approved",
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specification)
_g.add_node("compliance", verify_regulatory_compliance)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compliance")
_g.add_edge("compliance", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
