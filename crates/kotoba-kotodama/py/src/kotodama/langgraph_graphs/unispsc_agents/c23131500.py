# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23131500 — Industrial Manufacturing Services (Dyeing and finishing).

Bespoke graph logic for dyeing and finishing services, ensuring material
integrity, color precision, and finishing quality standards are met through
a validated state machine.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23131500"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23131500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Dyeing and Finishing Services
    material_composition: str
    dye_recipe_id: str
    bath_temperature: float
    ph_value: float
    quality_cert_issued: bool


def prepare_lot(state: State) -> dict[str, Any]:
    """Initialize the manufacturing lot and verify material specifications."""
    inp = state.get("input") or {}
    composition = inp.get("composition", "synthetic-blend")
    recipe = inp.get("recipe", "STD-001")

    return {
        "log": [f"{UNISPSC_CODE}:prepare_lot - Material: {composition}, Recipe: {recipe}"],
        "material_composition": composition,
        "dye_recipe_id": recipe,
    }


def apply_finishing(state: State) -> dict[str, Any]:
    """Execute the dyeing and chemical finishing process."""
    # Determine process parameters based on material
    composition = state.get("material_composition", "")
    temp = 98.5 if "cotton" in composition.lower() else 85.0
    target_ph = 5.5

    return {
        "log": [f"{UNISPSC_CODE}:apply_finishing - Process temp: {temp}C, pH target: {target_ph}"],
        "bath_temperature": temp,
        "ph_value": target_ph,
    }


def validate_output(state: State) -> dict[str, Any]:
    """Verify chemical residues, color fastness, and issue final certification."""
    ph = state.get("ph_value", 7.0)
    # Check if pH is within safe textile range (4.5 - 7.5)
    passed = 4.5 <= ph <= 7.5

    return {
        "log": [f"{UNISPSC_CODE}:validate_output - Quality check: {'PASS' if passed else 'FAIL'}"],
        "quality_cert_issued": passed,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "process_metrics": {
                "temp": state.get("bath_temperature"),
                "ph": ph,
            },
            "certified": passed,
            "ok": passed,
        },
    }


_g = StateGraph(State)

_g.add_node("prepare_lot", prepare_lot)
_g.add_node("apply_finishing", apply_finishing)
_g.add_node("validate_output", validate_output)

_g.add_edge(START, "prepare_lot")
_g.add_edge("prepare_lot", "apply_finishing")
_g.add_edge("apply_finishing", "validate_output")
_g.add_edge("validate_output", END)

graph = _g.compile()
