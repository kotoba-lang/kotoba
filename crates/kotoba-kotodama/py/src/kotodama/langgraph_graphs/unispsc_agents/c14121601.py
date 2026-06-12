# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14121601 — Agent.
Bespoke logic for chemical agents used in paper manufacturing (Segment 14).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14121601"
UNISPSC_TITLE = "Agent"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14121601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for paper production agents
    viscosity_cp: float
    ph_balance: float
    concentration_ratio: float
    is_stable: bool


def analyze_composition(state: State) -> dict[str, Any]:
    """Analyze the chemical properties of the agent."""
    inp = state.get("input") or {}
    viscosity = float(inp.get("viscosity", 150.0))
    ph = float(inp.get("ph", 7.0))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition -> viscosity={viscosity}, ph={ph}"],
        "viscosity_cp": viscosity,
        "ph_balance": ph,
    }


def verify_stability(state: State) -> dict[str, Any]:
    """Verify if the agent remains stable within temperature and pH bounds."""
    ph = state.get("ph_balance", 7.0)
    # Agents in paper making often require a specific pH range (e.g., 4.5 to 8.5)
    stable = 4.0 <= ph <= 9.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_stability -> stable={stable}"],
        "is_stable": stable,
        "concentration_ratio": 0.15 if stable else 0.0,
    }


def finalize_specification(state: State) -> dict[str, Any]:
    """Emit the final technical specification for the agent."""
    is_stable = state.get("is_stable", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified_stable": is_stable,
            "viscosity": state.get("viscosity_cp"),
            "ph": state.get("ph_balance"),
            "status": "ready" if is_stable else "rejected",
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_composition)
_g.add_node("verify", verify_stability)
_g.add_node("finalize", finalize_specification)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
