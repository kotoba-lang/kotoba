# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101502 — Bulk transporters (segment 24).

Bespoke graph logic for handling bulk transport operations, including cargo
inspection, vessel assignment, and dispatch clearance for heavy machinery.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101502"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    cargo_weight_tons: float
    material_category: str
    is_hazardous: bool
    assigned_carrier_id: str
    inspection_passed: bool


def validate_manifest(state: State) -> dict[str, Any]:
    """Validate the transport manifest and cargo specifications."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight_tons", 0.0))
    category = str(inp.get("category", "dry_bulk"))
    hazardous = inp.get("hazardous", False) or category.lower() in ["chemicals", "fuel"]

    return {
        "log": [f"{UNISPSC_CODE}:validate_manifest"],
        "cargo_weight_tons": weight,
        "material_category": category,
        "is_hazardous": hazardous,
        "inspection_passed": weight > 0,
    }


def assign_carrier(state: State) -> dict[str, Any]:
    """Select a suitable bulk carrier based on material and weight."""
    weight = state.get("cargo_weight_tons", 0.0)
    is_haz = state.get("is_hazardous", False)

    if is_haz:
        carrier = "SPEC-HAZ-V3"
    elif weight > 50000:
        carrier = "MAX-LOAD-CAP-01"
    else:
        carrier = "FLEX-CARRIER-09"

    return {
        "log": [f"{UNISPSC_CODE}:assign_carrier"],
        "assigned_carrier_id": carrier,
    }


def finalize_dispatch(state: State) -> dict[str, Any]:
    """Generate final clearance and emit the result."""
    carrier = state.get("assigned_carrier_id", "PENDING")
    passed = state.get("inspection_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_dispatch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "APPROVED" if passed else "REJECTED",
            "carrier_id": carrier,
            "timestamp": "2026-05-23T14:00:00Z",
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_manifest)
_g.add_node("assign", assign_carrier)
_g.add_node("finalize", finalize_dispatch)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assign")
_g.add_edge("assign", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
