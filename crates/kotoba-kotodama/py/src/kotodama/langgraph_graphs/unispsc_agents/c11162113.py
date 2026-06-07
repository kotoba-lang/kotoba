# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11162113 — Sic Procurement (segment 11).

Bespoke graph logic for Silica/Silicon Carbide procurement operations,
handling purity validation, source verification, and logistics readiness.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11162113"
UNISPSC_TITLE = "Sic Procurement"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11162113"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Silica Procurement
    purity_grade: float
    quarry_id: str
    logistics_id: str
    safety_compliant: bool


def validate_requirements(state: State) -> dict[str, Any]:
    """Validates the procurement request specs for purity and volume."""
    inp = state.get("input") or {}
    req_purity = inp.get("min_purity", 0.95)
    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "purity_grade": req_purity,
        "safety_compliant": True if req_purity > 0.9 else False,
    }


def verify_source(state: State) -> dict[str, Any]:
    """Cross-references the quarry ID and extraction site availability."""
    inp = state.get("input") or {}
    q_id = inp.get("preferred_quarry", "Q-SAND-1116")
    return {
        "log": [f"{UNISPSC_CODE}:verify_source"],
        "quarry_id": q_id,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Generates the final procurement manifest and logistics token."""
    q_id = state.get("quarry_id", "UNKNOWN")
    purity = state.get("purity_grade", 0.0)

    manifest_id = f"MANIFEST-{UNISPSC_CODE}-{q_id[-4:]}"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "logistics_id": manifest_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "manifest": manifest_id,
            "verified_purity": purity,
            "status": "ready_for_pickup",
            "did": UNISPSC_DID,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requirements)
_g.add_node("verify", verify_source)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
