# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25131705 — Drone Procure (segment 25).
Specialized procurement agent for unmanned aerial vehicles (UAVs).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25131705"
UNISPSC_TITLE = "Drone Procure"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25131705"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    uav_specs: dict[str, Any]
    vendor_selection: list[str]
    compliance_verified: bool
    procurement_auth_token: str


def analyze_uav_requirements(state: State) -> dict[str, Any]:
    """Validates payload, range, and operational environment for drone procurement."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})

    # Default specifications if none provided
    if not specs:
        specs = {"category": "commercial", "payload_kg": 2.5, "range_km": 10.0}

    return {
        "log": [f"{UNISPSC_CODE}:analyze_uav_requirements"],
        "uav_specs": specs,
    }


def source_uav_vendors(state: State) -> dict[str, Any]:
    """Matches specifications against pre-approved UAV manufacturers."""
    specs = state.get("uav_specs") or {}
    category = specs.get("category", "commercial")

    vendors = []
    if category == "commercial":
        vendors = ["AeroLogistics", "SkyCapture Corp"]
    elif category == "industrial":
        vendors = ["HeavyLift UAV", "StructureInspect Systems"]
    else:
        vendors = ["Generic UAV Systems"]

    return {
        "log": [f"{UNISPSC_CODE}:source_uav_vendors"],
        "vendor_selection": vendors,
    }


def verify_procurement_compliance(state: State) -> dict[str, Any]:
    """Checks for local aviation authority registration and safety certifications."""
    specs = state.get("uav_specs") or {}
    # Simulate a compliance check based on weight/payload
    is_heavy = specs.get("payload_kg", 0) > 25.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_procurement_compliance"],
        "compliance_verified": not is_heavy,  # Mock logic: heavy drones need manual review
        "procurement_auth_token": "AUTH-25131705-TEMP" if not is_heavy else "PENDING-REVIEW",
    }


def execute_procurement_emit(state: State) -> dict[str, Any]:
    """Finalizes the procurement state and returns the acquisition manifest."""
    vendors = state.get("vendor_selection", [])
    verified = state.get("compliance_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:execute_procurement_emit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_id": state.get("procurement_auth_token"),
            "vendors": vendors,
            "status": "APPROVED" if verified else "REJECTED_BY_COMPLIANCE",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_uav_requirements)
_g.add_node("source", source_uav_vendors)
_g.add_node("verify", verify_procurement_compliance)
_g.add_node("emit", execute_procurement_emit)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "source")
_g.add_edge("source", "verify")
_g.add_edge("verify", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
