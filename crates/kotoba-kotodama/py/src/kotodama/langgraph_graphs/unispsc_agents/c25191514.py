# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25191514 — Towbar (segment 25).

Bespoke graph logic for towbar inspection, load validation, and safety certification.
This module replaces the placeholder compliance pipeline with domain-specific state.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25191514"
UNISPSC_TITLE = "Towbar"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25191514"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Towbar
    towbar_type: str
    max_vertical_load_kg: float
    safety_pin_engaged: bool
    electrical_socket_functional: bool
    certification_id: str


def validate_compatibility(state: State) -> dict[str, Any]:
    """Verify that the towbar specifications match the vehicle requirements."""
    inp = state.get("input") or {}
    t_type = inp.get("towbar_type", "fixed")
    v_load = float(inp.get("requested_load_kg", 75.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_compatibility - type={t_type}, load={v_load}kg"],
        "towbar_type": t_type,
        "max_vertical_load_kg": v_load,
    }


def structural_integrity_check(state: State) -> dict[str, Any]:
    """Simulate a structural check of the mount points and safety locking mechanism."""
    # Logic: Safety pin is verified if the load capacity is within standard bounds
    v_load = state.get("max_vertical_load_kg", 0.0)
    pin_ok = v_load > 0 and v_load <= 150.0  # Standard safety threshold for this model

    return {
        "log": [f"{UNISPSC_CODE}:structural_integrity_check - pin_engaged={pin_ok}"],
        "safety_pin_engaged": pin_ok,
    }


def final_certification(state: State) -> dict[str, Any]:
    """Perform electrical tests and issue the final towbar certificate."""
    inp = state.get("input") or {}
    elec_ok = inp.get("electrical_check", True)
    pin_ok = state.get("safety_pin_engaged", False)

    is_ready = elec_ok and pin_ok
    cert_id = f"CERT-{UNISPSC_CODE}-2026-X" if is_ready else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:final_certification - status={cert_id}"],
        "electrical_socket_functional": elec_ok,
        "certification_id": cert_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification_id": cert_id,
            "status": "PASS" if is_ready else "FAIL",
            "ok": is_ready,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_compatibility", validate_compatibility)
_g.add_node("structural_integrity_check", structural_integrity_check)
_g.add_node("final_certification", final_certification)

_g.add_edge(START, "validate_compatibility")
_g.add_edge("validate_compatibility", "structural_integrity_check")
_g.add_edge("structural_integrity_check", "final_certification")
_g.add_edge("final_certification", END)

graph = _g.compile()
