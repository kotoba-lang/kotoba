# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111713 — Battery (segment 26).

Bespoke logic for battery specification validation and hazard assessment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111713"
UNISPSC_TITLE = "Battery"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111713"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    voltage_v: float
    chemistry: str
    capacity_mah: int
    is_hazardous: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Extracts and validates battery specifications from input."""
    inp = state.get("input") or {}
    voltage = inp.get("voltage", 0.0)
    chem = inp.get("chemistry", "unknown")
    cap = inp.get("capacity", 0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "voltage_v": float(voltage),
        "chemistry": str(chem),
        "capacity_mah": int(cap),
    }


def assess_hazards(state: State) -> dict[str, Any]:
    """Assesses hazardous material status based on battery chemistry."""
    chem = state.get("chemistry", "").lower()
    # Identification of common hazardous battery chemistries
    hazardous_types = {"lithium", "lead-acid", "cadmium", "li-ion", "ni-cd"}
    is_haz = any(h in chem for h in hazardous_types)

    return {
        "log": [f"{UNISPSC_CODE}:assess_hazards"],
        "is_hazardous": is_haz,
    }


def finalize_asset(state: State) -> dict[str, Any]:
    """Finalizes the battery asset record with safety metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "voltage_v": state.get("voltage_v"),
                "chemistry": state.get("chemistry"),
                "capacity_mah": state.get("capacity_mah"),
            },
            "safety": {
                "is_hazardous": state.get("is_hazardous"),
                "disposal_protocol": "hazardous_waste" if state.get("is_hazardous") else "standard",
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("assess_hazards", assess_hazards)
_g.add_node("finalize_asset", finalize_asset)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "assess_hazards")
_g.add_edge("assess_hazards", "finalize_asset")
_g.add_edge("finalize_asset", END)

graph = _g.compile()
