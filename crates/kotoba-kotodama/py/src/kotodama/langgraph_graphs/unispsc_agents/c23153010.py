# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153010 — Removal jig (segment 23).
Bespoke logic for jig identification, extraction force monitoring, and part integrity verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153010"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153010"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Removal jig operations
    jig_identifier: str
    alignment_verified: bool
    extraction_force_kn: float
    integrity_status: str


def identify_jig(state: State) -> dict[str, Any]:
    """Identifies the specific removal jig and verifies its mechanical alignment."""
    inp = state.get("input") or {}
    jig_id = inp.get("jig_id", "JIG-23153010-001")
    is_aligned = inp.get("alignment_data", {}).get("status") == "OPTIMAL"

    return {
        "log": [f"{UNISPSC_CODE}:identify_jig"],
        "jig_identifier": jig_id,
        "alignment_verified": is_aligned,
    }


def execute_removal(state: State) -> dict[str, Any]:
    """Monitors the force applied by the jig during the part removal process."""
    if not state.get("alignment_verified"):
        return {
            "log": [f"{UNISPSC_CODE}:execute_removal:aborted_due_to_alignment"],
            "extraction_force_kn": 0.0,
            "integrity_status": "NOT_STARTED",
        }

    # Simulate extraction force measurement
    force = 14.2  # Measured force in kilo-Newtons
    return {
        "log": [f"{UNISPSC_CODE}:execute_removal:completed"],
        "extraction_force_kn": force,
        "integrity_status": "REMOVED" if force < 18.0 else "DAMAGED",
    }


def verify_result(state: State) -> dict[str, Any]:
    """Finalizes the agent execution by validating the outcome of the removal."""
    ok = state.get("integrity_status") == "REMOVED"

    return {
        "log": [f"{UNISPSC_CODE}:verify_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "force_applied": state.get("extraction_force_kn"),
            "status": "success" if ok else "failure",
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("identify_jig", identify_jig)
_g.add_node("execute_removal", execute_removal)
_g.add_node("verify_result", verify_result)

_g.add_edge(START, "identify_jig")
_g.add_edge("identify_jig", "execute_removal")
_g.add_edge("execute_removal", "verify_result")
_g.add_edge("verify_result", END)

graph = _g.compile()
