# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10161901 — Raw Material (segment 10).

Bespoke graph logic for handling raw material lifecycles, focusing on
origin verification, quality assessment, and batch tracking for
primary production resources.
"""

from __future__ import annotations

import operator

from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10161901"
UNISPSC_TITLE = "Raw Material"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10161901"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Raw Material lifecycle
    batch_identifier: str
    quality_grade: str
    origin_verified: bool
    quarantine_status: str


def validate_origin(state: State) -> dict[str, Any]:
    """Validates the geographical and regulatory origin of the raw material."""
    inp = state.get("input") or {}
    batch = inp.get("batch_id", "RMAT-UNKNOWN")
    # Logic: Verify origin from input or default to True for simulation purposes
    origin_ok = "origin" in inp or inp.get("auto_verify", False)

    return {
        "log": [f"{UNISPSC_CODE}:validate_origin -> {batch} (verified: {origin_ok})"],
        "batch_identifier": batch,
        "origin_verified": origin_ok,
    }


def assessment_process(state: State) -> dict[str, Any]:
    """Conducts a physical assessment of the material quality and purity."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "Standard")
    # Simulation: assign quarantine status based on grade strings
    q_status = "CLEARED" if grade.upper() != "CONTAMINATED" else "HOLD"

    return {
        "log": [f"{UNISPSC_CODE}:assessment_process -> {grade} ({q_status})"],
        "quality_grade": grade,
        "quarantine_status": q_status,
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Finalizes material entry into inventory systems and emits agent results."""
    verified = state.get("origin_verified", False)
    q_status = state.get("quarantine_status", "UNKNOWN")
    is_ok = verified and q_status == "CLEARED"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory -> success: {is_ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch": state.get("batch_identifier"),
            "status": "ACCEPTED" if is_ok else "REJECTED",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_origin)
_g.add_node("assess", assessment_process)
_g.add_node("finalize", finalize_inventory)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
