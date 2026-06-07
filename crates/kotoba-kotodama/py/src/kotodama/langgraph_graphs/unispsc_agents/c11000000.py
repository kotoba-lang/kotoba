# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11000000 — Raw Material (segment 11).

Bespoke graph logic for handling raw materials, specifically focused on
provenance verification, material purity inspection, and grading certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11000000"
UNISPSC_TITLE = "Raw Material"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11000000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Raw Material
    origin_verified: bool
    material_purity: float
    storage_compliance: bool
    grade_assigned: str


def verify_provenance(state: State) -> dict[str, Any]:
    """Validates the source and chain of custody for the raw material."""
    inp = state.get("input") or {}
    source_id = inp.get("source_id", "UNKNOWN")
    # Simulation: specific source IDs are pre-verified
    is_verified = source_id.startswith("SRCE-")
    return {
        "log": [f"{UNISPSC_CODE}:verify_provenance: source={source_id} verified={is_verified}"],
        "origin_verified": is_verified,
    }


def analyze_composition(state: State) -> dict[str, Any]:
    """Performs laboratory-style analysis on purity and contaminants."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity_rating", 0.85))
    temp_check = inp.get("storage_temp", 20.0)

    # Material must be stored within a safe range for Raw Material stability
    is_compliant = 0.0 <= temp_check <= 30.0

    # Assign grade based on purity
    grade = "INDUSTRIAL"
    if purity > 0.98:
        grade = "PHARMA"
    elif purity > 0.95:
        grade = "FOOD"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition: purity={purity} grade={grade}"],
        "material_purity": purity,
        "storage_compliance": is_compliant,
        "grade_assigned": grade,
    }


def certify_batch(state: State) -> dict[str, Any]:
    """Finalizes the state and emits the formal certification result."""
    verified = state.get("origin_verified", False)
    compliant = state.get("storage_compliance", False)
    grade = state.get("grade_assigned", "UNGRADED")

    ok = verified and compliant

    return {
        "log": [f"{UNISPSC_CODE}:certify_batch: final_ok={ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "CERTIFIED" if ok else "REJECTED",
            "metadata": {
                "grade": grade,
                "purity": state.get("material_purity"),
                "compliance": compliant
            }
        },
    }


_g = StateGraph(State)
_g.add_node("verify", verify_provenance)
_g.add_node("analyze", analyze_composition)
_g.add_node("certify", certify_batch)

_g.add_edge(START, "verify")
_g.add_edge("verify", "analyze")
_g.add_edge("analyze", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
