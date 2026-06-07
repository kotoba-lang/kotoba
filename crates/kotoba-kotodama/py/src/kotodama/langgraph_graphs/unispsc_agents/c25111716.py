# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111716 — Vessel (segment 25).

Bespoke graph logic for maritime vessel operations, handling hull integrity
inspections, cargo manifest verification, and port docking authorization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111716"
UNISPSC_TITLE = "Vessel"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111716"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Vessel-specific domain fields
    vessel_id: str
    hull_integrity_status: str
    manifest_verified: bool
    docking_clearance: bool


def inspect_hull(state: State) -> dict[str, Any]:
    """Inspects the physical condition of the vessel's hull."""
    inp = state.get("input") or {}
    v_id = inp.get("vessel_id", "V-999-DEFAULT")
    # Assume inspection passes unless a specific failure is reported in input
    status = inp.get("hull_report", "CERTIFIED_CLEAR")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_hull: {v_id} -> {status}"],
        "vessel_id": v_id,
        "hull_integrity_status": status,
    }


def verify_manifest(state: State) -> dict[str, Any]:
    """Validates the cargo and crew manifest for customs compliance."""
    inp = state.get("input") or {}
    manifest_data = inp.get("manifest", {})

    # Logic: Manifest is verified if hull is clear and manifest data exists
    hull_ok = state.get("hull_integrity_status") == "CERTIFIED_CLEAR"
    is_valid = bool(manifest_data) and hull_ok

    return {
        "log": [f"{UNISPSC_CODE}:verify_manifest: result={is_valid}"],
        "manifest_verified": is_valid,
    }


def authorize_docking(state: State) -> dict[str, Any]:
    """Final check to authorize the vessel for port docking."""
    is_verified = state.get("manifest_verified", False)
    hull_status = state.get("hull_integrity_status")

    clearance = is_verified and (hull_status == "CERTIFIED_CLEAR")

    return {
        "log": [f"{UNISPSC_CODE}:authorize_docking: clearance={clearance}"],
        "docking_clearance": clearance,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "vessel_id": state.get("vessel_id"),
            "docking_status": "APPROVED" if clearance else "DENIED",
            "did": UNISPSC_DID,
            "ok": clearance,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_hull", inspect_hull)
_g.add_node("verify_manifest", verify_manifest)
_g.add_node("authorize_docking", authorize_docking)

_g.add_edge(START, "inspect_hull")
_g.add_edge("inspect_hull", "verify_manifest")
_g.add_edge("verify_manifest", "authorize_docking")
_g.add_edge("authorize_docking", END)

graph = _g.compile()
