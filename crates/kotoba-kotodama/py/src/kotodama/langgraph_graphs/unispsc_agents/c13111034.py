# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111034 — Nuclear Component (segment 13).

Bespoke graph logic for handling nuclear component safety verification
and lifecycle management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111034"
UNISPSC_TITLE = "Nuclear Component"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111034"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    radiation_level: float
    containment_status: str
    safety_clearance: bool
    batch_id: str


def safety_audit(state: State) -> dict[str, Any]:
    """Inspects the component for radiation levels and containment integrity."""
    inp = state.get("input") or {}
    rad = inp.get("radiation_level", 0.0)
    seal = inp.get("seal_integrity", 1.0)

    log_msg = f"{UNISPSC_CODE}:safety_audit [rad={rad}, seal={seal}]"

    return {
        "log": [log_msg],
        "radiation_level": rad,
        "containment_status": "INTACT" if seal > 0.95 else "COMPROMISED",
        "batch_id": inp.get("batch_id", "UNKNOWN-NC"),
    }


def verify_containment(state: State) -> dict[str, Any]:
    """Performs deep verification of the nuclear containment structures."""
    status = state.get("containment_status")
    rad = state.get("radiation_level", 0.0)

    is_safe = (status == "INTACT") and (rad < 50.0)

    return {
        "log": [f"{UNISPSC_CODE}:verify_containment [is_safe={is_safe}]"],
        "safety_clearance": is_safe,
    }


def release_record(state: State) -> dict[str, Any]:
    """Finalizes the component status and emits the actor response."""
    safe = state.get("safety_clearance", False)
    status = state.get("containment_status", "UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:release_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "safety_verified": safe,
            "containment_state": status,
            "ok": safe,
        },
    }


_g = StateGraph(State)
_g.add_node("safety_audit", safety_audit)
_g.add_node("verify_containment", verify_containment)
_g.add_node("release_record", release_record)

_g.add_edge(START, "safety_audit")
_g.add_edge("safety_audit", "verify_containment")
_g.add_edge("verify_containment", "release_record")
_g.add_edge("release_record", END)

graph = _g.compile()
