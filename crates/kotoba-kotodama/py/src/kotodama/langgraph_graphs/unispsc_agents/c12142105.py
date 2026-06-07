# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12142105 — Nickel (segment 12).
Specialized logic for validating nickel purity, grading, and form factor for metal inventory.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12142105"
UNISPSC_TITLE = "Nickel"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12142105"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Nickel
    purity_percentage: float
    material_form: str
    is_battery_grade: bool
    lot_certification_id: str


def validate_purity(state: State) -> dict[str, Any]:
    """Inspects input for assay data and extracts purity percentage."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 99.0))
    cert_id = str(inp.get("cert_id", "UNCERTIFIED"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_purity(purity={purity}%)"],
        "purity_percentage": purity,
        "lot_certification_id": cert_id,
    }


def determine_grade(state: State) -> dict[str, Any]:
    """Classifies the nickel based on purity levels and intended form."""
    purity = state.get("purity_percentage", 0.0)
    inp = state.get("input") or {}

    # Nickel with purity > 99.9% is typically considered battery grade
    battery_grade = purity >= 99.9
    form = inp.get("form", "ingot")

    return {
        "log": [f"{UNISPSC_CODE}:determine_grade(battery_grade={battery_grade}, form={form})"],
        "is_battery_grade": battery_grade,
        "material_form": form,
    }


def record_metal_state(state: State) -> dict[str, Any]:
    """Finalizes the inventory record for the Nickel lot."""
    return {
        "log": [f"{UNISPSC_CODE}:record_metal_state"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specifications": {
                "purity": state.get("purity_percentage"),
                "form": state.get("material_form"),
                "battery_grade": state.get("is_battery_grade"),
                "cert_id": state.get("lot_certification_id"),
            },
            "status": "verified",
        },
    }


_g = StateGraph(State)

_g.add_node("validate_purity", validate_purity)
_g.add_node("determine_grade", determine_grade)
_g.add_node("record_metal_state", record_metal_state)

_g.add_edge(START, "validate_purity")
_g.add_edge("validate_purity", "determine_grade")
_g.add_edge("determine_grade", "record_metal_state")
_g.add_edge("record_metal_state", END)

graph = _g.compile()
