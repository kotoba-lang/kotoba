# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111600 — Rescue Craft (segment 25).

Bespoke graph implementation for managing rescue craft deployment, crew
manifest verification, and emergency equipment readiness assessments.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111600"
UNISPSC_TITLE = "Rescue Craft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Rescue Craft
    vessel_id: str
    crew_manifest_verified: bool
    deployment_readiness: str
    emergency_equipment_check: bool


def validate_manifest(state: State) -> dict[str, Any]:
    """Validates the crew manifest and identifies the rescue vessel."""
    inp = state.get("input") or {}
    vessel_id = inp.get("vessel_id", "RESCUE-DEFAULT")
    crew = inp.get("crew_list", [])

    # Requirement: At least 3 crew members for active rescue duty
    is_verified = len(crew) >= 3

    return {
        "log": [f"{UNISPSC_CODE}:validate_manifest"],
        "vessel_id": vessel_id,
        "crew_manifest_verified": is_verified,
    }


def assess_readiness(state: State) -> dict[str, Any]:
    """Checks emergency equipment status and determines deployment state."""
    inp = state.get("input") or {}
    eq_check = inp.get("equipment_check", False)
    manifest_ok = state.get("crew_manifest_verified", False)

    # Logic: Ready only if crew is verified and equipment check passed
    if manifest_ok and eq_check:
        readiness = "READY_FOR_DISPATCH"
    elif manifest_ok:
        readiness = "EQUIPMENT_PENDING"
    else:
        readiness = "CREW_INCOMPLETE"

    return {
        "log": [f"{UNISPSC_CODE}:assess_readiness"],
        "emergency_equipment_check": eq_check,
        "deployment_readiness": readiness,
    }


def finalize_dispatch(state: State) -> dict[str, Any]:
    """Prepares the final result based on readiness and compliance."""
    readiness = state.get("deployment_readiness")
    is_ready = readiness == "READY_FOR_DISPATCH"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_dispatch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "vessel_id": state.get("vessel_id"),
            "dispatch_status": readiness,
            "ok": is_ready,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_manifest", validate_manifest)
_g.add_node("assess_readiness", assess_readiness)
_g.add_node("finalize_dispatch", finalize_dispatch)

_g.add_edge(START, "validate_manifest")
_g.add_edge("validate_manifest", "assess_readiness")
_g.add_edge("assess_readiness", "finalize_dispatch")
_g.add_edge("finalize_dispatch", END)

graph = _g.compile()
