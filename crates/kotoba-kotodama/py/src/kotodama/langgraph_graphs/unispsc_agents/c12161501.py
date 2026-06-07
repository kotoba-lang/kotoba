# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12161501"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12161501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    catalyst_type: str
    active_component: str
    operating_temp_c: int
    thermal_stability_limit: int
    is_safe: bool


def characterize_agent(state: State) -> dict[str, Any]:
    """Analyze the chemical composition and intended substrate of the catalyst."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:characterize_agent"],
        "catalyst_type": inp.get("type", "heterogeneous"),
        "active_component": inp.get("metal", "Platinum"),
        "thermal_stability_limit": inp.get("limit", 850),
    }


def validate_thermal_load(state: State) -> dict[str, Any]:
    """Evaluate if the catalyst can withstand the required reaction temperature."""
    inp = state.get("input") or {}
    target_temp = int(inp.get("reaction_temp", 450))
    limit = state.get("thermal_stability_limit", 0)

    is_safe = target_temp <= limit
    return {
        "log": [f"{UNISPSC_CODE}:validate_thermal_load"],
        "operating_temp_c": target_temp,
        "is_safe": is_safe,
    }


def synthesize_specification(state: State) -> dict[str, Any]:
    """Finalize the catalyst performance profile and safety status."""
    is_safe = state.get("is_safe", False)
    metal = state.get("active_component", "Unknown")

    # Calculate an efficacy score based on safety and metal type
    efficacy = 0.94 if is_safe else 0.05
    if metal.lower() == "platinum":
        efficacy += 0.02

    return {
        "log": [f"{UNISPSC_CODE}:synthesize_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metal_base": metal,
            "operational_safety": "PASS" if is_safe else "FAIL",
            "efficacy_index": round(min(efficacy, 1.0), 3),
            "status": "ready_for_deployment" if is_safe else "high_risk_rejection",
        },
    }


_g = StateGraph(State)
_g.add_node("characterize_agent", characterize_agent)
_g.add_node("validate_thermal_load", validate_thermal_load)
_g.add_node("synthesize_specification", synthesize_specification)

_g.add_edge(START, "characterize_agent")
_g.add_edge("characterize_agent", "validate_thermal_load")
_g.add_edge("validate_thermal_load", "synthesize_specification")
_g.add_edge("synthesize_specification", END)

graph = _g.compile()
