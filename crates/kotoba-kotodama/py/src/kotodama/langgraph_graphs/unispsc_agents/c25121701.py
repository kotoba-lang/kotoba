# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25121701 — Rail System (segment 25).

Bespoke logic for planning, safety verification, and deployment of rail infrastructure.
"""

from __future__ import annotations

import operator
# Ensure operator.add is available for Annotated log
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25121701"
UNISPSC_TITLE = "Rail System"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25121701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Rail System
    track_gauge_mm: int
    electrification_type: str
    safety_integrity_level: int
    clearance_verified: bool


def plan_infrastructure(state: State) -> dict[str, Any]:
    """Determines basic rail parameters based on input requirements."""
    inp = state.get("input") or {}
    # Default to standard gauge (1435mm) if not specified
    gauge = inp.get("gauge", 1435)
    traction = inp.get("traction", "25kV AC Overhead")

    return {
        "log": [f"{UNISPSC_CODE}:plan_infrastructure"],
        "track_gauge_mm": gauge,
        "electrification_type": traction,
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Checks gauge and electrification against safety standards."""
    gauge = state.get("track_gauge_mm", 0)
    # Rail standards validation
    is_standard = gauge in [1067, 1435, 1520, 1676]
    sil_level = 4 if is_standard else 1

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance"],
        "safety_integrity_level": sil_level,
        "clearance_verified": is_standard,
    }


def deploy_system(state: State) -> dict[str, Any]:
    """Finalizes the rail system deployment status."""
    is_ok = state.get("clearance_verified", False) and state.get("safety_integrity_level", 0) >= 3

    return {
        "log": [f"{UNISPSC_CODE}:deploy_system"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": is_ok,
            "system_spec": {
                "gauge": state.get("track_gauge_mm"),
                "traction": state.get("electrification_type"),
                "sil": state.get("safety_integrity_level")
            }
        },
    }


_g = StateGraph(State)

_g.add_node("plan", plan_infrastructure)
_g.add_node("verify", verify_compliance)
_g.add_node("deploy", deploy_system)

_g.add_edge(START, "plan")
_g.add_edge("plan", "verify")
_g.add_edge("verify", "deploy")
_g.add_edge("deploy", END)

graph = _g.compile()
