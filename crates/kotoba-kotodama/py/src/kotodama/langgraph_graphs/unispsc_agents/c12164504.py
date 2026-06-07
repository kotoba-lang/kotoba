# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12164504 — Material (segment 12).

Bespoke implementation for handling biological material consignment. This graph
replaces the placeholder with logic appropriate for Segment 12 material
inspection, quality assessment, and inventory recording.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12164504"
UNISPSC_TITLE = "Material"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12164504"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for biological material
    lot_id: str
    taxonomic_verification: bool
    quality_grade: str
    quarantine_status: str


def validate_consignment(state: State) -> dict[str, Any]:
    """Validates the incoming material data and lot identification."""
    inp = state.get("input") or {}
    lot = inp.get("lot_id", "LOT-GEN-001")
    tax_verified = bool(inp.get("taxonomic_data"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_consignment"],
        "lot_id": lot,
        "taxonomic_verification": tax_verified,
    }


def assess_quality(state: State) -> dict[str, Any]:
    """Simulates a quality assessment based on moisture and purity levels."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 0.95))

    # Determine grade based on purity thresholds
    if purity > 0.98:
        grade = "ELITE"
    elif purity > 0.90:
        grade = "COMMERCIAL"
    else:
        grade = "SUBSTANDARD"

    return {
        "log": [f"{UNISPSC_CODE}:assess_quality"],
        "quality_grade": grade,
    }


def determine_disposition(state: State) -> dict[str, Any]:
    """Determines if the material requires quarantine or is ready for release."""
    tax_ok = state.get("taxonomic_verification", False)
    grade = state.get("quality_grade", "UNKNOWN")

    # Logic for disposition
    if tax_ok and grade != "SUBSTANDARD":
        status = "RELEASED"
    else:
        status = "QUARANTINED"

    return {
        "log": [f"{UNISPSC_CODE}:determine_disposition"],
        "quarantine_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "lot_id": state.get("lot_id"),
            "grade": grade,
            "status": status,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_consignment)
_g.add_node("assess", assess_quality)
_g.add_node("disposition", determine_disposition)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "disposition")
_g.add_edge("disposition", END)

graph = _g.compile()
