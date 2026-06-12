# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25171719 — Brake (segment 25).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25171719"
UNISPSC_TITLE = "Brake"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25171719"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Brake actor
    rotor_wear_status: str
    pad_friction_index: float
    hydraulic_integrity: bool
    thermal_capacity_joules: int


def check_mechanical_integrity(state: State) -> dict[str, Any]:
    """Validates physical brake components."""
    inp = state.get("input") or {}
    wear = inp.get("wear_percentage", 10)
    status = "nominal" if wear < 75 else "critical"
    return {
        "log": [f"{UNISPSC_CODE}:check_mechanical_integrity"],
        "rotor_wear_status": status,
        "pad_friction_index": 0.42 if status == "nominal" else 0.15,
    }


def simulate_emergency_stop(state: State) -> dict[str, Any]:
    """Calculates stopping efficiency under load."""
    friction = state.get("pad_friction_index", 0.0)
    integrity = friction > 0.3
    capacity = 50000 if integrity else 10000
    return {
        "log": [f"{UNISPSC_CODE}:simulate_emergency_stop"],
        "hydraulic_integrity": integrity,
        "thermal_capacity_joules": capacity,
    }


def generate_compliance_report(state: State) -> dict[str, Any]:
    """Finalizes the brake inspection result."""
    is_safe = state.get("hydraulic_integrity", False)
    return {
        "log": [f"{UNISPSC_CODE}:generate_compliance_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "APPROVED" if is_safe else "REJECTED",
            "metrics": {
                "wear": state.get("rotor_wear_status"),
                "joules": state.get("thermal_capacity_joules"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("check_mechanical_integrity", check_mechanical_integrity)
_g.add_node("simulate_emergency_stop", simulate_emergency_stop)
_g.add_node("generate_compliance_report", generate_compliance_report)

_g.add_edge(START, "check_mechanical_integrity")
_g.add_edge("check_mechanical_integrity", "simulate_emergency_stop")
_g.add_edge("simulate_emergency_stop", "generate_compliance_report")
_g.add_edge("generate_compliance_report", END)

graph = _g.compile()
