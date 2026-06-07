# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10161603 — Crop (segment 10).

Bespoke graph logic for agricultural crop management, including field assessment,
yield calculation, and readiness reporting.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10161603"
UNISPSC_TITLE = "Crop"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10161603"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    soil_moisture_level: float
    pest_pressure_score: float
    calculated_yield: float
    harvest_approval: bool


def assess_conditions(state: State) -> dict[str, Any]:
    """Inspects environmental factors affecting the crop."""
    inp = state.get("input") or {}
    moisture = float(inp.get("moisture", 0.5))
    pests = float(inp.get("pests", 0.1))
    return {
        "log": [f"{UNISPSC_CODE}:assess_conditions"],
        "soil_moisture_level": moisture,
        "pest_pressure_score": pests,
    }


def analyze_growth(state: State) -> dict[str, Any]:
    """Determines yield potential and harvest readiness based on conditions."""
    moisture = state.get("soil_moisture_level", 0.0)
    pests = state.get("pest_pressure_score", 1.0)

    # Healthy growth requires adequate moisture and low pest pressure
    growth_factor = moisture * (1.0 - pests)
    est_yield = max(0.0, growth_factor * 500.0)

    # Threshold for harvest readiness
    ready = growth_factor > 0.4

    return {
        "log": [f"{UNISPSC_CODE}:analyze_growth"],
        "calculated_yield": round(est_yield, 2),
        "harvest_approval": ready,
    }


def emit_report(state: State) -> dict[str, Any]:
    """Generates the final actor output with crop metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "yield_kg": state.get("calculated_yield"),
                "harvest_ready": state.get("harvest_approval"),
            },
            "status": "completed",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("assess_conditions", assess_conditions)
_g.add_node("analyze_growth", analyze_growth)
_g.add_node("emit_report", emit_report)

_g.add_edge(START, "assess_conditions")
_g.add_edge("assess_conditions", "analyze_growth")
_g.add_edge("analyze_growth", "emit_report")
_g.add_edge("emit_report", END)

graph = _g.compile()
