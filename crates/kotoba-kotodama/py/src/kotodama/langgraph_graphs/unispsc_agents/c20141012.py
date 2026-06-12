# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20141012.
Domain-specific logic for Mining and Well Drilling Machinery (Segment 20).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141012"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141012"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for drilling equipment
    material_hardness: float
    operational_hours: int
    thermal_threshold_exceeded: bool
    maintenance_score: float


def validate_tooling_specs(state: State) -> dict[str, Any]:
    """Validates the physical specifications of the drilling tool."""
    inp = state.get("input") or {}
    hardness = float(inp.get("hardness_mohs", 7.0))
    hours = int(inp.get("hours", 0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_tooling_specs: hardness={hardness}"],
        "material_hardness": hardness,
        "operational_hours": hours,
    }


def analyze_mechanical_wear(state: State) -> dict[str, Any]:
    """Calculates wear and thermal status based on operational history."""
    hours = state.get("operational_hours", 0)
    hardness = state.get("material_hardness", 7.0)

    # Higher hardness tools last longer; wear increases with hours
    wear = (hours * 0.1) / (hardness / 5.0)
    thermal_issue = hours > 500 and hardness < 6.0

    return {
        "log": [f"{UNISPSC_CODE}:analyze_mechanical_wear: wear={wear:.2f}"],
        "maintenance_score": max(0.0, 100.0 - wear),
        "thermal_threshold_exceeded": thermal_issue,
    }


def generate_equipment_report(state: State) -> dict[str, Any]:
    """Finalizes the state into a structured result for the actor."""
    score = state.get("maintenance_score", 0.0)
    thermal_fail = state.get("thermal_threshold_exceeded", False)

    status = "OPTIMAL"
    if score < 70 or thermal_fail:
        status = "REPLACE_SOON"
    if score < 40:
        status = "DANGER_IMMEDIATE_REPLACEMENT"

    return {
        "log": [f"{UNISPSC_CODE}:generate_equipment_report: status={status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "maintenance_score": round(score, 2),
                "thermal_fail": thermal_fail,
                "operational_status": status
            },
            "ok": not thermal_fail and score > 20.0,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_tooling_specs)
_g.add_node("analyze", analyze_mechanical_wear)
_g.add_node("report", generate_equipment_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "report")
_g.add_edge("report", END)

graph = _g.compile()
