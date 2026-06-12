# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111901 — Clutch (segment 26).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111901"
UNISPSC_TITLE = "Clutch"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111901"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Clutch
    torque_capacity_nm: float
    engagement_rpm: int
    wear_coefficient: float
    safety_margin: float


def validate_mechanical_specs(state: State) -> dict[str, Any]:
    """Analyzes the input mechanical specifications for the clutch unit."""
    inp = state.get("input") or {}
    torque = float(inp.get("torque", 450.0))
    rpm = int(inp.get("rpm", 2200))
    return {
        "log": [f"{UNISPSC_CODE}:validate_mechanical_specs -> torque={torque}Nm, rpm={rpm}"],
        "torque_capacity_nm": torque,
        "engagement_rpm": rpm,
    }


def evaluate_friction_wear(state: State) -> dict[str, Any]:
    """Calculates simulated friction wear based on engagement dynamics."""
    rpm = state.get("engagement_rpm", 0)
    torque = state.get("torque_capacity_nm", 0.0)
    # Simple wear heuristic for power transmission
    wear = (rpm * torque) / 1_500_000.0
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_friction_wear -> wear_coeff={wear:.6f}"],
        "wear_coefficient": wear,
    }


def finalize_engineering_report(state: State) -> dict[str, Any]:
    """Produces the final validation and safety report for the clutch assembly."""
    wear = state.get("wear_coefficient", 0.0)
    margin = 3.0 - (wear * 2.0)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_engineering_report -> safety_margin={margin:.2f}"],
        "safety_margin": margin,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "analysis": {
                "wear_coefficient": round(wear, 6),
                "safety_margin": round(margin, 2),
                "compliance": "PASS" if margin > 1.5 else "FAIL"
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_mechanical_specs)
_g.add_node("evaluate", evaluate_friction_wear)
_g.add_node("finalize", finalize_engineering_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "evaluate")
_g.add_edge("evaluate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
