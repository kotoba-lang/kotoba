# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23121506 — Compressor (segment 23).

Bespoke graph logic for Compressor actor, managing operational state,
pressure ratings, and maintenance schedules.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23121506"
UNISPSC_TITLE = "Compressor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23121506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    pressure_rating_psi: float
    compressor_model: str
    maintenance_due: bool
    efficiency_grade: str
    safety_valve_status: str


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the incoming compressor specifications and model data."""
    inp = state.get("input") or {}
    model = inp.get("model", "CP-2300-X")
    psi = float(inp.get("psi_rating", 150.0))
    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "compressor_model": model,
        "pressure_rating_psi": psi,
        "safety_valve_status": "nominal" if psi <= 200.0 else "critical",
    }


def analyze_performance(state: State) -> dict[str, Any]:
    """Calculates efficiency and determines maintenance requirements."""
    psi = state.get("pressure_rating_psi", 0.0)
    # Mock analysis logic
    grade = "Tier A" if psi >= 120.0 else "Tier B"
    maint = psi > 180.0 # High pressure models require more frequent checks

    return {
        "log": [f"{UNISPSC_CODE}:analyze_performance"],
        "efficiency_grade": grade,
        "maintenance_due": maint,
    }


def finalize_asset_state(state: State) -> dict[str, Any]:
    """Constructs the final operational report for the compressor agent."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_state"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "segment": UNISPSC_SEGMENT,
            "metadata": {
                "model": state.get("compressor_model"),
                "efficiency": state.get("efficiency_grade"),
                "psi": state.get("pressure_rating_psi"),
                "maintenance_required": state.get("maintenance_due"),
                "valve_state": state.get("safety_valve_status"),
            },
            "status": "operational",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("analyze", analyze_performance)
_g.add_node("finalize", finalize_asset_state)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
