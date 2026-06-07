# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12142206 — Agent (segment 12).

This bespoke LangGraph implementation manages the state transitions for a
chemical agent, covering specification validation, stability assessment,
and safety certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12142206"
UNISPSC_TITLE = "Agent"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12142206"


class State(TypedDict, total=False):
    """Bespoke state for the Agent actor."""
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for segment 12 chemical agents
    chemical_formula: str
    concentration_level: float
    safety_clearance: bool
    stability_score: float
    storage_conditions: str


def validate_specs(state: State) -> dict[str, Any]:
    """Validate chemical specifications from input."""
    inp = state.get("input") or {}
    formula = str(inp.get("formula", "H2SO4"))
    conc = float(inp.get("concentration", 1.0))
    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "chemical_formula": formula,
        "concentration_level": conc,
    }


def assess_stability(state: State) -> dict[str, Any]:
    """Assess the stability of the agent based on concentration."""
    conc = state.get("concentration_level", 0.0)
    # Higher concentration implies lower stability for this simulation
    stability = max(0.0, 100.0 - (conc * 10.0))
    cleared = stability > 40.0
    return {
        "log": [f"{UNISPSC_CODE}:assess_stability"],
        "stability_score": stability,
        "safety_clearance": cleared,
    }


def authorize_usage(state: State) -> dict[str, Any]:
    """Authorize the usage and set storage conditions."""
    cleared = state.get("safety_clearance", False)
    stability = state.get("stability_score", 0.0)

    conditions = "Cold Storage" if stability < 70.0 else "Ambient"

    return {
        "log": [f"{UNISPSC_CODE}:authorize_usage"],
        "storage_conditions": conditions,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "formula": state.get("chemical_formula"),
            "authorized": cleared,
            "recommended_storage": conditions,
            "ok": cleared,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("assess", assess_stability)
_g.add_node("authorize", authorize_usage)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "authorize")
_g.add_edge("authorize", END)

graph = _g.compile()
