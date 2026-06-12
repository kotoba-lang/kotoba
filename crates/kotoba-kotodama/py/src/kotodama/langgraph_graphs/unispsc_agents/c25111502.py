# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111502 — Vessel (segment 25).

Bespoke LangGraph implementation for Vessel management, seaworthiness verification,
and maritime registration workflows.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111502"
UNISPSC_TITLE = "Vessel"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for "Vessel"
    vessel_type: str
    imo_number: str
    hull_integrity_score: int
    is_seaworthy: bool
    registration_status: str


def validate_manifest(state: State) -> dict[str, Any]:
    """Validates the input manifest and extracts vessel identity."""
    inp = state.get("input") or {}
    v_type = inp.get("vessel_type", "commercial_cargo")
    imo = inp.get("imo_number", "9000000")

    return {
        "log": [f"{UNISPSC_CODE}:validate_manifest"],
        "vessel_type": v_type,
        "imo_number": imo,
        "registration_status": "pending_inspection"
    }


def assess_seaworthiness(state: State) -> dict[str, Any]:
    """Simulates a technical assessment of the vessel's hull and safety systems."""
    # Simulate an assessment logic based on input or defaults
    score = 85
    seaworthy = score >= 70

    return {
        "log": [f"{UNISPSC_CODE}:assess_seaworthiness"],
        "hull_integrity_score": score,
        "is_seaworthy": seaworthy
    }


def certify_vessel(state: State) -> dict[str, Any]:
    """Finalizes the vessel status and generates the registration certificate."""
    is_ok = state.get("is_seaworthy", False)
    status = "certified" if is_ok else "quarantined"

    return {
        "log": [f"{UNISPSC_CODE}:certify_vessel"],
        "registration_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "vessel_type": state.get("vessel_type"),
            "imo_number": state.get("imo_number"),
            "hull_score": state.get("hull_integrity_score"),
            "seaworthy": is_ok,
            "status": status,
            "did": UNISPSC_DID,
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_manifest", validate_manifest)
_g.add_node("assess_seaworthiness", assess_seaworthiness)
_g.add_node("certify_vessel", certify_vessel)

_g.add_edge(START, "validate_manifest")
_g.add_edge("validate_manifest", "assess_seaworthiness")
_g.add_edge("assess_seaworthiness", "certify_vessel")
_g.add_edge("certify_vessel", END)

graph = _g.compile()
