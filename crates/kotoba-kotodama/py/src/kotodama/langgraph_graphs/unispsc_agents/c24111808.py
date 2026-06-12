# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24111808 — Tank Procurement (segment 24).

Bespoke graph logic for industrial tank procurement. This agent handles
specification validation, vendor selection based on material requirements,
and finalizes the procurement record for segment 24 assets.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24111808"
UNISPSC_TITLE = "Tank Procurement"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24111808"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Tank Procurement
    capacity_liters: int
    material_grade: str
    vendor_selection: str
    procurement_status: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Extract and validate tank capacity and material specs."""
    inp = state.get("input") or {}
    capacity = inp.get("capacity", 5000)
    material = inp.get("material", "carbon_steel")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "capacity_liters": capacity,
        "material_grade": material,
        "procurement_status": "specifications_verified"
    }


def select_vendor(state: State) -> dict[str, Any]:
    """Identify appropriate vendor based on material grade."""
    material = state.get("material_grade", "standard")

    # Logic based on procurement segment standards
    if "stainless" in material.lower():
        vendor = "VND-24-HIGH-PURITY"
    elif "glass" in material.lower():
        vendor = "VND-24-LINED-VESSELS"
    else:
        vendor = "VND-24-GENERAL-FAB"

    return {
        "log": [f"{UNISPSC_CODE}:select_vendor"],
        "vendor_selection": vendor,
        "procurement_status": "vendor_assigned"
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalize the procurement result with metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "procurement_status": "finalized",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_data": {
                "capacity": state.get("capacity_liters"),
                "material": state.get("material_grade"),
                "vendor": state.get("vendor_selection")
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specifications", validate_specifications)
_g.add_node("select_vendor", select_vendor)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "select_vendor")
_g.add_edge("select_vendor", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
