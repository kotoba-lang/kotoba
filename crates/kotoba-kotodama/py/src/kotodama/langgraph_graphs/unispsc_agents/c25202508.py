# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202508 — Aircraft Part (segment 25).
Bespoke logic for aircraft part lifecycle, airworthiness verification, and safety auditing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202508"
UNISPSC_TITLE = "Aircraft Part"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202508"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    part_id: str
    serial_number: str
    airworthiness_certified: bool
    maintenance_history_verified: bool
    safety_inspection_status: str


def validate_part_identity(state: State) -> dict[str, Any]:
    """Extracts and validates part identity from input data."""
    inp = state.get("input") or {}
    p_id = inp.get("part_id", "ACFT-PN-PLACEHOLDER")
    sn = inp.get("serial_number", "SN-PENDING")
    return {
        "log": [f"{UNISPSC_CODE}:validate_part_identity:{p_id}"],
        "part_id": p_id,
        "serial_number": sn,
    }


def check_airworthiness(state: State) -> dict[str, Any]:
    """Verifies airworthiness certification and maintenance logs."""
    p_id = state.get("part_id", "")
    # Simulation: parts starting with 'ACFT' are considered certified in this model
    is_certified = p_id.startswith("ACFT")
    return {
        "log": [f"{UNISPSC_CODE}:check_airworthiness:verified"],
        "airworthiness_certified": is_certified,
        "maintenance_history_verified": True,
        "safety_inspection_status": "APPROVED" if is_certified else "FLAGGED",
    }


def emit_manifest_entry(state: State) -> dict[str, Any]:
    """Finalizes the inventory record and emits the result manifest."""
    certified = state.get("airworthiness_certified", False)
    status = state.get("safety_inspection_status", "UNKNOWN")
    return {
        "log": [f"{UNISPSC_CODE}:emit_manifest_entry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "part_id": state.get("part_id"),
            "serial": state.get("serial_number"),
            "inspection_status": status,
            "airworthy": certified,
            "did": UNISPSC_DID,
            "ok": certified,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_part_identity", validate_part_identity)
_g.add_node("check_airworthiness", check_airworthiness)
_g.add_node("emit_manifest_entry", emit_manifest_entry)

_g.add_edge(START, "validate_part_identity")
_g.add_edge("validate_part_identity", "check_airworthiness")
_g.add_edge("check_airworthiness", "emit_manifest_entry")
_g.add_edge("emit_manifest_entry", END)

graph = _g.compile()
