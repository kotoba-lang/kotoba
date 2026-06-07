# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101101 — Motor (segment 26).

This bespoke LangGraph implementation handles state transitions for motor
specification validation, performance analysis, and inventory manifest generation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101101"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101101"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Motor
    voltage_rating: int
    rotations_per_minute: int
    efficiency_score: float
    winding_insulation_class: str
    thermal_protection_active: bool


def inspect_specifications(state: State) -> dict[str, Any]:
    """Validates the electrical and mechanical requirements of the motor unit."""
    inp = state.get("input") or {}
    voltage = inp.get("voltage", 230)
    rpm = inp.get("rpm", 1750)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "voltage_rating": voltage,
        "rotations_per_minute": rpm,
        "thermal_protection_active": voltage > 400
    }


def analyze_performance(state: State) -> dict[str, Any]:
    """Computes efficiency metrics and insulation standards based on input specs."""
    rpm = state.get("rotations_per_minute", 0)
    voltage = state.get("voltage_rating", 0)

    # Calculate a mock efficiency score
    efficiency = 0.92 if rpm > 1200 and voltage >= 208 else 0.84
    insulation = "Class F" if voltage > 240 else "Class B"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_performance"],
        "efficiency_score": efficiency,
        "winding_insulation_class": insulation
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Generates the final actor response including the motor's technical profile."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "profile": {
                "voltage": state.get("voltage_rating"),
                "rpm": state.get("rotations_per_minute"),
                "efficiency": state.get("efficiency_score"),
                "insulation": state.get("winding_insulation_class"),
                "thermal_protection": state.get("thermal_protection_active")
            },
            "status": "certified",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_specifications)
_g.add_node("analyze", analyze_performance)
_g.add_node("finalize", finalize_manifest)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
