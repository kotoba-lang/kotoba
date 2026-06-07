# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12171605"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12171605"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Catalyst agents
    reaction_mechanism: str
    activation_threshold: float
    acceleration_factor: float
    thermal_stability_k: float
    catalytic_yield: float


def validate_substrate(state: State) -> dict[str, Any]:
    """Validates the input substrate and reaction conditions for compatibility."""
    inp = state.get("input") or {}
    mechanism = inp.get("mechanism", "oxidation")
    threshold = float(inp.get("threshold", 45.5))

    return {
        "log": [f"{UNISPSC_CODE}:validate_substrate(mechanism={mechanism})"],
        "reaction_mechanism": mechanism,
        "activation_threshold": threshold,
    }


def process_catalysis(state: State) -> dict[str, Any]:
    """Simulates the catalytic process reducing activation energy."""
    # Determine acceleration based on threshold
    base_factor = 12.5
    stability = 373.15  # Kelvin (100 Celsius)

    # Calculate simulated yield based on mechanism
    current_mech = state.get("reaction_mechanism", "oxidation")
    calculated_yield = 0.945 if current_mech == "oxidation" else 0.88

    return {
        "log": [f"{UNISPSC_CODE}:process_catalysis(yield={calculated_yield})"],
        "acceleration_factor": base_factor,
        "thermal_stability_k": stability,
        "catalytic_yield": calculated_yield,
    }


def emit_agent_result(state: State) -> dict[str, Any]:
    """Finalizes the catalytic reaction data and emits the agent result."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_agent_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "catalysis": {
                "mechanism": state.get("reaction_mechanism"),
                "yield": state.get("catalytic_yield"),
                "acceleration": state.get("acceleration_factor"),
            },
            "status": "completed",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_substrate)
_g.add_node("catalyze", process_catalysis)
_g.add_node("emit", emit_agent_result)

_g.add_edge(START, "validate")
_g.add_edge("validate", "catalyze")
_g.add_edge("catalyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
