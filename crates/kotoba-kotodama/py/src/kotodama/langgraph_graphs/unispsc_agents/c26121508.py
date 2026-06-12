# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26121508 — Wire (segment 26).

Bespoke graph logic for handling electrical wire specifications, insulation
validation, and load capacity assessment within the Etz Hayyim actor model.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26121508"
UNISPSC_TITLE = "Wire"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26121508"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Wire
    gauge_awg: int
    material: str
    insulation_rating_celsius: int
    max_amperage: float
    specification_valid: bool


def validate_specification(state: State) -> dict[str, Any]:
    """Extracts and validates wire physical properties from input."""
    inp = state.get("input") or {}
    gauge = inp.get("gauge_awg", 12)
    material = inp.get("material", "Copper").capitalize()
    insulation = inp.get("insulation_rating", 75)

    # Simple validation: common gauges are 0-40 AWG
    is_valid = 0 <= gauge <= 40 and material in ["Copper", "Aluminum"]

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "gauge_awg": gauge,
        "material": material,
        "insulation_rating_celsius": insulation,
        "specification_valid": is_valid,
    }


def assess_load_capacity(state: State) -> dict[str, Any]:
    """Calculates theoretical max amperage based on gauge and material."""
    gauge = state.get("gauge_awg", 14)
    material = state.get("material", "Copper")

    # Heuristic ampacity calculation (simplified NEC table logic)
    base_amps = {14: 15.0, 12: 20.0, 10: 30.0, 8: 40.0, 6: 55.0}.get(gauge, 10.0)

    # Aluminum typically carries ~77% the current of copper for same gauge
    factor = 1.0 if material == "Copper" else 0.77
    calculated_amps = base_amps * factor

    return {
        "log": [f"{UNISPSC_CODE}:assess_load_capacity"],
        "max_amperage": calculated_amps,
    }


def finalize_asset_data(state: State) -> dict[str, Any]:
    """Prepares the final result dictionary for the Wire commodity."""
    is_valid = state.get("specification_valid", False)

    result = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "did": UNISPSC_DID,
        "properties": {
            "gauge_awg": state.get("gauge_awg"),
            "material": state.get("material"),
            "max_amperage": state.get("max_amperage"),
            "insulation_rating": state.get("insulation_rating_celsius"),
        },
        "compliance": "NEC-Simulated" if is_valid else "Incomplete",
        "status": "ready" if is_valid else "draft",
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_data"],
        "result": result,
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specification)
_g.add_node("assess", assess_load_capacity)
_g.add_node("finalize", finalize_asset_data)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
