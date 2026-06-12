# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122840 — Bearing (segment 20).

Bespoke logic for bearing specification validation, mechanical load assessment,
and certification processing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122840"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122840"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Bearings
    bore_diameter_mm: float
    dynamic_load_rating_kn: float
    bearing_type: str
    lubrication_requirement: str
    is_compliant: bool


def inspect_mechanical_specs(state: State) -> dict[str, Any]:
    """Validates core mechanical dimensions and load ratings."""
    inp = state.get("input") or {}
    bore = float(inp.get("bore_diameter_mm", 0.0))
    load = float(inp.get("dynamic_load_rating_kn", 0.0))
    b_type = str(inp.get("bearing_type", "Deep Groove Ball"))

    # Simple validation logic
    is_compliant = bore > 2.0 and load > 0.5

    return {
        "log": [f"{UNISPSC_CODE}:inspect_mechanical_specs"],
        "bore_diameter_mm": bore,
        "dynamic_load_rating_kn": load,
        "bearing_type": b_type,
        "is_compliant": is_compliant,
    }


def determine_lubrication_profile(state: State) -> dict[str, Any]:
    """Assigns lubrication requirements based on bearing type and size."""
    bore = state.get("bore_diameter_mm", 0.0)
    b_type = state.get("bearing_type", "")

    if "Roller" in b_type or bore > 100:
        lubrication = "Heavy-Duty Industrial Grease"
    else:
        lubrication = "Light Synthetic Oil"

    return {
        "log": [f"{UNISPSC_CODE}:determine_lubrication_profile"],
        "lubrication_requirement": lubrication,
    }


def certify_and_emit(state: State) -> dict[str, Any]:
    """Finalizes the certification record for the bearing component."""
    is_compliant = state.get("is_compliant", False)

    summary = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "certification_status": "APPROVED" if is_compliant else "REJECTED",
        "metadata": {
            "bore": state.get("bore_diameter_mm"),
            "load_rating": state.get("dynamic_load_rating_kn"),
            "lubrication": state.get("lubrication_requirement"),
            "type": state.get("bearing_type"),
        },
        "ok": is_compliant,
    }

    return {
        "log": [f"{UNISPSC_CODE}:certify_and_emit"],
        "result": summary,
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_mechanical_specs)
_g.add_node("lubrication", determine_lubrication_profile)
_g.add_node("certify", certify_and_emit)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "lubrication")
_g.add_edge("lubrication", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
