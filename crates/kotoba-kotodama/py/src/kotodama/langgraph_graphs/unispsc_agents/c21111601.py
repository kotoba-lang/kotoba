# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21111601 — Agent (segment 21).

Bespoke logic for managing agricultural and biological control agents within
the farming and forestry machinery ecosystem.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21111601"
UNISPSC_TITLE = "Agent"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21111601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Agricultural/Biological Agents
    agent_category: str
    target_pathogen: str
    application_frequency: str
    safety_clearance: bool
    potency_index: float


def inspect_parameters(state: State) -> dict[str, Any]:
    """Evaluates the incoming agent specifications and potency."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:inspect_parameters"],
        "agent_category": inp.get("category", "biological_control"),
        "target_pathogen": inp.get("target", "soil_borne_fungi"),
        "potency_index": float(inp.get("concentration", 0.85)),
    }


def calibrate_application(state: State) -> dict[str, Any]:
    """Calibrates the frequency and safety protocols for the agent."""
    potency = state.get("potency_index", 0.0)
    # Higher potency requires less frequent but more cautious application
    freq = "bi-weekly" if potency > 0.5 else "weekly"
    is_safe = True if potency < 0.95 else False

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_application"],
        "application_frequency": freq,
        "safety_clearance": is_safe,
    }


def formulate_result(state: State) -> dict[str, Any]:
    """Finalizes the agent management state and produces the deployment result."""
    return {
        "log": [f"{UNISPSC_CODE}:formulate_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "deployment_plan": {
                "category": state.get("agent_category"),
                "target": state.get("target_pathogen"),
                "frequency": state.get("application_frequency"),
                "safe_to_deploy": state.get("safety_clearance"),
            },
            "status": "ready_for_distribution",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_parameters)
_g.add_node("calibrate", calibrate_application)
_g.add_node("formulate", formulate_result)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calibrate")
_g.add_edge("calibrate", "formulate")
_g.add_edge("formulate", END)

graph = _g.compile()
