# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10171602 — Mineral Fertilizer (segment 10).

Bespoke graph for mineral fertilizer processing, handling nutrient analysis,
moisture verification, and safety certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10171602"
UNISPSC_TITLE = "Mineral Fertilizer"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10171602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Mineral Fertilizer
    nutrient_analysis: dict[str, float]
    moisture_percentage: float
    safety_standards_met: bool
    batch_reference: str


def validate_composition(state: State) -> dict[str, Any]:
    """Inspects raw nutrient data and assigns a batch reference."""
    inp = state.get("input") or {}
    analysis = inp.get("analysis", {"N": 0.0, "P": 0.0, "K": 0.0})
    return {
        "log": [f"{UNISPSC_CODE}:validate_composition"],
        "nutrient_analysis": analysis,
        "batch_reference": inp.get("batch_id", "MIN-FERT-DEFAULT"),
    }


def check_stability(state: State) -> dict[str, Any]:
    """Verifies moisture content and general safety stability."""
    inp = state.get("input") or {}
    moisture = inp.get("moisture", 5.0)
    # Typical threshold for mineral fertilizer stability to prevent caking
    is_stable = moisture < 10.0
    return {
        "log": [f"{UNISPSC_CODE}:check_stability"],
        "moisture_percentage": moisture,
        "safety_standards_met": is_stable,
    }


def prepare_manifest(state: State) -> dict[str, Any]:
    """Generates the final result manifest based on analysis and stability."""
    is_ok = state.get("safety_standards_met", False)
    return {
        "log": [f"{UNISPSC_CODE}:prepare_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch": state.get("batch_reference"),
            "analysis": state.get("nutrient_analysis"),
            "status": "CERTIFIED" if is_ok else "QUARANTINED",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_composition", validate_composition)
_g.add_node("check_stability", check_stability)
_g.add_node("prepare_manifest", prepare_manifest)

_g.add_edge(START, "validate_composition")
_g.add_edge("validate_composition", "check_stability")
_g.add_edge("check_stability", "prepare_manifest")
_g.add_edge("prepare_manifest", END)

graph = _g.compile()
