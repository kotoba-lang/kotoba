# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23271602 — Soldering (segment 23).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271602"
UNISPSC_TITLE = "Soldering"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Soldering operations
    iron_temp_celsius: int
    flux_type: str
    alloy_specification: str
    joint_integrity_score: float
    inspection_passed: bool


def configure_station(state: State) -> dict[str, Any]:
    """Initializes tool parameters and verifies material readiness."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:configure_station"],
        "iron_temp_celsius": inp.get("temp", 360),
        "flux_type": inp.get("flux", "No-Clean"),
        "alloy_specification": inp.get("alloy", "Sn96.5Ag3.0Cu0.5"),
    }


def execute_thermal_bond(state: State) -> dict[str, Any]:
    """Applies heat and alloy to create the intermetallic layer."""
    temp = state.get("iron_temp_celsius", 0)
    # Validating thermal window for the specified alloy
    score = 0.95 if 340 <= temp <= 380 else 0.40
    return {
        "log": [f"{UNISPSC_CODE}:execute_thermal_bond"],
        "joint_integrity_score": score,
        "inspection_passed": score > 0.80,
    }


def validate_and_emit(state: State) -> dict[str, Any]:
    """Performs visual inspection and finalizes the agent output."""
    passed = state.get("inspection_passed", False)
    return {
        "log": [f"{UNISPSC_CODE}:validate_and_emit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "APPROVED" if passed else "REJECTED",
            "telemetry": {
                "final_temp": state.get("iron_temp_celsius"),
                "integrity": state.get("joint_integrity_score"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("configure_station", configure_station)
_g.add_node("execute_thermal_bond", execute_thermal_bond)
_g.add_node("validate_and_emit", validate_and_emit)

_g.add_edge(START, "configure_station")
_g.add_edge("configure_station", "execute_thermal_bond")
_g.add_edge("execute_thermal_bond", "validate_and_emit")
_g.add_edge("validate_and_emit", END)

graph = _g.compile()
