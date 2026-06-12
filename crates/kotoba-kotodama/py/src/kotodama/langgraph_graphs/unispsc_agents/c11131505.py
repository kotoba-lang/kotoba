# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11131505 — Mineral (segment 11).

Bespoke graph logic for handling mineral resource data, including assay
validation, grade classification, and inventory recording for Earth-based
mineral products.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11131505"
UNISPSC_TITLE = "Mineral"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11131505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Minerals
    extraction_method: str
    purity_percentage: float
    resource_category: str
    assay_valid: bool
    inventory_lot_id: str


def validate_assay(state: State) -> dict[str, Any]:
    """Validates the mineral assay data from the input."""
    inp = state.get("input") or {}
    purity = inp.get("purity", 0.0)
    method = inp.get("method", "quarrying")
    lot_id = inp.get("lot_id", "MIN-DEFAULT-001")

    is_valid = 0.0 <= purity <= 100.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_assay"],
        "purity_percentage": purity,
        "extraction_method": method,
        "inventory_lot_id": lot_id,
        "assay_valid": is_valid,
    }


def classify_grade(state: State) -> dict[str, Any]:
    """Classifies the mineral resource based on its purity assay."""
    purity = state.get("purity_percentage", 0.0)

    if purity > 98.0:
        category = "Refined/Ultra-High Purity"
    elif purity > 85.0:
        category = "Industrial Grade"
    elif purity > 60.0:
        category = "Raw Ore / Feedstock"
    else:
        category = "Low Grade Aggregate"

    return {
        "log": [f"{UNISPSC_CODE}:classify_grade"],
        "resource_category": category,
    }


def inventory_record(state: State) -> dict[str, Any]:
    """Records the final state into the result payload."""
    return {
        "log": [f"{UNISPSC_CODE}:inventory_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "lot_id": state.get("inventory_lot_id"),
            "purity": state.get("purity_percentage"),
            "category": state.get("resource_category"),
            "method": state.get("extraction_method"),
            "valid": state.get("assay_valid"),
            "status": "recorded_to_ledger",
        },
    }


_g = StateGraph(State)

_g.add_node("validate_assay", validate_assay)
_g.add_node("classify_grade", classify_grade)
_g.add_node("inventory_record", inventory_record)

_g.add_edge(START, "validate_assay")
_g.add_edge("validate_assay", "classify_grade")
_g.add_edge("classify_grade", "inventory_record")
_g.add_edge("inventory_record", END)

graph = _g.compile()
