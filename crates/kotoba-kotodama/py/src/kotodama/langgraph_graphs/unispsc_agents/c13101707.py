# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13101707 — Commodity.

Bespoke logic for handling resin and material commodities within segment 13.
This agent manages specification validation, quality assessment, and procurement
status for resin-based commodity materials.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13101707"
UNISPSC_TITLE = "Commodity"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13101707"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Commodity (Resins/Materials)
    material_spec: dict[str, Any]
    quality_grade: str
    inventory_available: bool
    sds_verified: bool


def intake(state: State) -> dict[str, Any]:
    """Validates the incoming commodity specification and safety data."""
    inp = state.get("input") or {}
    spec = inp.get("specification", {})
    has_sds = inp.get("safety_data_sheet", False)

    return {
        "log": [f"{UNISPSC_CODE}:intake"],
        "material_spec": spec,
        "sds_verified": bool(has_sds),
    }


def assess_quality(state: State) -> dict[str, Any]:
    """Determines the quality grade based on material specifications."""
    spec = state.get("material_spec") or {}
    purity = spec.get("purity", 0.0)

    grade = "Standard"
    if purity > 0.99:
        grade = "High-Purity"
    elif purity < 0.90:
        grade = "Industrial"

    return {
        "log": [f"{UNISPSC_CODE}:assess_quality"],
        "quality_grade": grade,
        "inventory_available": True,  # Simulated inventory check
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the commodity record and sets the result payload."""
    grade = state.get("quality_grade", "Unknown")
    sds = state.get("sds_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "grade": grade,
            "compliant": sds,
            "status": "Ready for Procurement" if sds else "Pending SDS Verification",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("intake", intake)
_g.add_node("assess_quality", assess_quality)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "intake")
_g.add_edge("intake", "assess_quality")
_g.add_edge("assess_quality", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
