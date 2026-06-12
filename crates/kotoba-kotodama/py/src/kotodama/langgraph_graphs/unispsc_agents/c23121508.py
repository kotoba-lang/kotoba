# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23121508 — Robot Procurement (segment 23).

Bespoke logic for robot procurement automation, handling specification
validation, vendor evaluation, and procurement finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23121508"
UNISPSC_TITLE = "Robot Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23121508"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific state for Robot Procurement
    specs: dict[str, Any]
    compliance_verified: bool
    budget_limit: float
    vendor_shortlist: list[str]


def validate_requirements(state: State) -> dict[str, Any]:
    """Validates the technical specifications of the robot requested."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})

    # Basic validation: requires degree-of-freedom (dof) and payload specs
    has_critical_specs = "dof" in specs and "payload" in specs

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "specs": specs,
        "compliance_verified": has_critical_specs,
    }


def evaluate_market(state: State) -> dict[str, Any]:
    """Analyzes market availability and budget constraints."""
    if not state.get("compliance_verified"):
        return {"log": [f"{UNISPSC_CODE}:evaluate_market_skipped"]}

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_market"],
        "budget_limit": 75000.0,
        "vendor_shortlist": ["RoboSystems Inc", "Global Automation"],
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement transaction record."""
    is_ready = state.get("compliance_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "APPROVED" if is_ready else "PENDING_TECHNICAL_DATA",
            "ok": is_ready,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requirements)
_g.add_node("market", evaluate_market)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "market")
_g.add_edge("market", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
