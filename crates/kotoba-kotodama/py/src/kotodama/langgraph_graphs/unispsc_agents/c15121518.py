# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15121518 — Alloy Processing (segment 15).

Bespoke graph logic for alloy metallurgical processing, including
composition verification, thermal treatment simulation, and batch certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15121518"
UNISPSC_TITLE = "Alloy Processing"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15121518"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Alloy Processing
    alloy_composition: dict[str, float]
    target_temperature: int
    cooling_protocol: str
    quality_threshold_met: bool


def analyze_composition(state: State) -> dict[str, Any]:
    """Analyzes the raw material input for chemical composition."""
    inp = state.get("input") or {}
    materials = inp.get("materials", {"Fe": 0.95, "C": 0.05})
    temp = inp.get("temp", 1550)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition"],
        "alloy_composition": materials,
        "target_temperature": temp,
    }


def thermal_treatment(state: State) -> dict[str, Any]:
    """Simulates the heating and cooling cycle of the alloy batch."""
    composition = state.get("alloy_composition", {})
    # Mock logic: Carbon content determines cooling protocol
    carbon = composition.get("C", 0.0)
    protocol = "Quench" if carbon > 0.02 else "Anneal"

    return {
        "log": [f"{UNISPSC_CODE}:thermal_treatment"],
        "cooling_protocol": protocol,
        "quality_threshold_met": 1400 < state.get("target_temperature", 0) < 1800,
    }


def finalize_batch(state: State) -> dict[str, Any]:
    """Finalizes the processing and emits the batch certification metadata."""
    success = state.get("quality_threshold_met", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "CERTIFIED" if success else "REJECTED",
            "protocol": state.get("cooling_protocol"),
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_composition)
_g.add_node("treat", thermal_treatment)
_g.add_node("finalize", finalize_batch)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "treat")
_g.add_edge("treat", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
