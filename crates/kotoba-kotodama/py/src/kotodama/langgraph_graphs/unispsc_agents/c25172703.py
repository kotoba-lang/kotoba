# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172703 — Marine Sys (segment 25).

Bespoke graph logic for marine system lifecycle management, including
hull inspection, propulsion verification, and final system certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172703"
UNISPSC_TITLE = "Marine Sys"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172703"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Marine Sys
    hull_integrity_status: str
    propulsion_verification: bool
    navigation_ready: bool
    vessel_class: str


def inspect_hull(state: State) -> dict[str, Any]:
    """Evaluates the structural integrity of the marine vessel hull."""
    inp = state.get("input") or {}
    hull_type = inp.get("hull_type", "unknown")
    status = "nominal" if hull_type != "unknown" else "pending_inspection"
    return {
        "log": [f"{UNISPSC_CODE}:hull_inspection:{status}"],
        "hull_integrity_status": status,
        "vessel_class": inp.get("class", "unclassified"),
    }


def verify_propulsion(state: State) -> dict[str, Any]:
    """Validates engine and propulsion mechanical readiness."""
    inp = state.get("input") or {}
    systems = inp.get("systems", [])
    is_verified = any(s in ["diesel", "electric", "nuclear", "outboard"] for s in systems)
    return {
        "log": [f"{UNISPSC_CODE}:propulsion_verification:{is_verified}"],
        "propulsion_verification": is_verified,
    }


def certify_vessel(state: State) -> dict[str, Any]:
    """Issues final marine system certification based on gathered telemetry."""
    hull_ok = state.get("hull_integrity_status") == "nominal"
    prop_ok = state.get("propulsion_verification", False)
    certified = hull_ok and prop_ok

    return {
        "log": [f"{UNISPSC_CODE}:certification:success={certified}"],
        "navigation_ready": certified,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "vessel_class": state.get("vessel_class"),
            "status": "Seaworthy" if certified else "Drydock Required",
            "hull": state.get("hull_integrity_status"),
            "propulsion_check": "passed" if prop_ok else "failed",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_hull", inspect_hull)
_g.add_node("verify_propulsion", verify_propulsion)
_g.add_node("certify_vessel", certify_vessel)

_g.add_edge(START, "inspect_hull")
_g.add_edge("inspect_hull", "verify_propulsion")
_g.add_edge("verify_propulsion", "certify_vessel")
_g.add_edge("certify_vessel", END)

graph = _g.compile()
