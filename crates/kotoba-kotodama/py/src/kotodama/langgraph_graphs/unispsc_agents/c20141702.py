# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20141702 — Mining (segment 20).

Bespoke LangGraph agent implementing geological assessment, safety validation,
and production forecasting for mining operations.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141702"
UNISPSC_TITLE = "Mining"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141702"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Mining domain fields
    extraction_method: str
    geological_survey_complete: bool
    safety_hazard_level: int
    operational_permit_id: str
    projected_yield_tonnes: float


def analyze_geological_data(state: State) -> dict[str, Any]:
    """Evaluates the initial input for geological viability and extraction method."""
    inp = state.get("input") or {}
    method = inp.get("method", "underground")
    survey = bool(inp.get("survey_data"))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_geological_data"],
        "extraction_method": method,
        "geological_survey_complete": survey,
    }


def assess_safety_and_risk(state: State) -> dict[str, Any]:
    """Determines safety hazards based on the extraction method and survey status."""
    method = state.get("extraction_method")
    survey = state.get("geological_survey_complete", False)

    # Calculate hazard level (0-10) based on method and data completeness
    hazard = 4
    if method == "underground":
        hazard += 3
    if not survey:
        hazard += 3

    return {
        "log": [f"{UNISPSC_CODE}:assess_safety_and_risk"],
        "safety_hazard_level": hazard,
        "operational_permit_id": f"PERMIT-{UNISPSC_CODE}-{'VALID' if hazard < 8 else 'HELD'}",
    }


def calculate_output_projection(state: State) -> dict[str, Any]:
    """Projects the total yield and finalizes the mining agent's state."""
    hazard = state.get("safety_hazard_level", 10)
    is_safe = hazard < 8

    yield_tonnes = 0.0
    if is_safe:
        # Base yield modified by safety coefficient
        yield_tonnes = 10000.0 * (1 - (hazard / 20.0))

    return {
        "log": [f"{UNISPSC_CODE}:calculate_output_projection"],
        "projected_yield_tonnes": round(yield_tonnes, 2),
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "hazard_level": hazard,
            "yield_estimate": round(yield_tonnes, 2),
            "ok": is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("geology", analyze_geological_data)
_g.add_node("safety", assess_safety_and_risk)
_g.add_node("projection", calculate_output_projection)

_g.add_edge(START, "geology")
_g.add_edge("geology", "safety")
_g.add_edge("safety", "projection")
_g.add_edge("projection", END)

graph = _g.compile()
