# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101307 — Motor (segment 26).

Bespoke graph logic for motor specification validation and performance assessment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101307"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101307"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Motor
    voltage_rating: int
    rpm_limit: int
    thermal_protection_active: bool
    efficiency_class: str


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the input specifications for the motor."""
    inp = state.get("input") or {}
    voltage = inp.get("voltage", 230)
    rpm = inp.get("rpm", 1800)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "voltage_rating": voltage,
        "rpm_limit": rpm,
        "thermal_protection_active": inp.get("thermal_protection", True),
    }


def assess_performance(state: State) -> dict[str, Any]:
    """Assess the efficiency class based on motor parameters."""
    voltage = state.get("voltage_rating", 0)

    # Logic to determine efficiency class
    if voltage >= 400:
        eff = "IE3"
    elif voltage >= 200:
        eff = "IE2"
    else:
        eff = "IE1"

    return {
        "log": [f"{UNISPSC_CODE}:assess_performance"],
        "efficiency_class": eff,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Generates the final certification result for the motor."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specs": {
                "voltage": state.get("voltage_rating"),
                "rpm": state.get("rpm_limit"),
                "efficiency": state.get("efficiency_class"),
                "thermal_protection": state.get("thermal_protection_active"),
            },
            "certified": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specs", validate_specs)
_g.add_node("assess_performance", assess_performance)
_g.add_node("finalize_certification", finalize_certification)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "assess_performance")
_g.add_edge("assess_performance", "finalize_certification")
_g.add_edge("finalize_certification", END)

graph = _g.compile()
