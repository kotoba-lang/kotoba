# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21100000 — Agri (segment 21).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21100000"
UNISPSC_TITLE = "Agri"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21100000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Agriculture
    crop_type: str
    soil_ph_level: float
    irrigation_required: bool
    expected_yield_kg: float
    last_inspection_date: str


def validate_environmental_input(state: State) -> dict[str, Any]:
    """Extracts basic agricultural parameters from input."""
    inp = state.get("input") or {}
    crop = str(inp.get("crop", "Maize"))
    ph = float(inp.get("ph", 6.5))
    return {
        "log": [f"{UNISPSC_CODE}:validate_environmental_input"],
        "crop_type": crop,
        "soil_ph_level": ph,
    }


def analyze_crop_viability(state: State) -> dict[str, Any]:
    """Analyzes soil pH and determines irrigation needs."""
    ph = state.get("soil_ph_level", 7.0)
    # Optimal pH for many crops is 6.0-7.5; outside this requires intervention
    needs_irrigation = ph > 7.2 or ph < 6.2
    yield_est = 5000.0 if not needs_irrigation else 3800.0
    return {
        "log": [f"{UNISPSC_CODE}:analyze_crop_viability"],
        "irrigation_required": needs_irrigation,
        "expected_yield_kg": yield_est,
        "last_inspection_date": "2026-05-23",
    }


def generate_agri_manifest(state: State) -> dict[str, Any]:
    """Finalizes the agricultural manifest for the agent result."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_agri_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "manifest": {
                "crop": state.get("crop_type"),
                "projected_yield_kg": state.get("expected_yield_kg"),
                "requires_irrigation": state.get("irrigation_required"),
                "inspection_timestamp": state.get("last_inspection_date"),
                "status": "VALIDATED",
            },
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_environmental_input)
_g.add_node("analyze", analyze_crop_viability)
_g.add_node("manifest", generate_agri_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "manifest")
_g.add_edge("manifest", END)

graph = _g.compile()
