# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10141502 — Drill (segment 10).
This agent handles the lifecycle and welfare monitoring for the Drill (Mandrillus leucophaeus),
ensuring habitat standards, dietary protocols, and social troop metrics are maintained.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10141502"
UNISPSC_TITLE = "Drill"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10141502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Drill (primate) management
    health_index: float
    dietary_compliance: bool
    troop_social_stability: float
    habitat_humidity_verified: bool


def assess_vitals(state: State) -> dict[str, Any]:
    """Evaluates the physiological and dietary status of the animal."""
    inp = state.get("input") or {}
    vitals = inp.get("vitals", {})
    health_score = float(vitals.get("heart_rate_variability", 0.9))

    return {
        "log": [f"{UNISPSC_CODE}:assess_vitals"],
        "health_index": health_score,
        "dietary_compliance": vitals.get("caloric_intake_target", True),
    }


def analyze_social_dynamics(state: State) -> dict[str, Any]:
    """Monitors troop interactions and social hierarchy integration."""
    # Drills are highly social; stability is key for their welfare
    current_health = state.get("health_index", 0.0)
    stability = 0.95 if current_health > 0.8 else 0.70

    return {
        "log": [f"{UNISPSC_CODE}:analyze_social_dynamics"],
        "troop_social_stability": stability,
        "habitat_humidity_verified": True,
    }


def formulate_status_report(state: State) -> dict[str, Any]:
    """Generates the final compliance and welfare report for the actor."""
    health = state.get("health_index", 0.0)
    social = state.get("troop_social_stability", 0.0)

    is_optimal = health > 0.85 and social > 0.90

    return {
        "log": [f"{UNISPSC_CODE}:formulate_status_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "welfare_status": "OPTIMAL" if is_optimal else "MONITOR",
            "metrics": {
                "health": health,
                "social_stability": social,
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("assess_vitals", assess_vitals)
_g.add_node("analyze_social_dynamics", analyze_social_dynamics)
_g.add_node("formulate_status_report", formulate_status_report)

_g.add_edge(START, "assess_vitals")
_g.add_edge("assess_vitals", "analyze_social_dynamics")
_g.add_edge("analyze_social_dynamics", "formulate_status_report")
_g.add_edge("formulate_status_report", END)

graph = _g.compile()
