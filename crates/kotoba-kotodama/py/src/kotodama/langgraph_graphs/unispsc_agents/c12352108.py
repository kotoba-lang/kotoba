# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12352108 — Chemical (segment 12).

Bespoke logic for chemical safety assessment, purity verification,
and material certification protocols within the segment 12 ontology.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352108"
UNISPSC_TITLE = "Chemical"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352108"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Chemical management
    purity_grade: str
    hazard_class: str
    safety_data_sheet_verified: bool
    quarantine_status: str


def verify_specifications(state: State) -> dict[str, Any]:
    """Validates chemical purity and safety documentation metadata."""
    inp = state.get("input") or {}
    purity = inp.get("purity", "Technical Grade")
    sds_id = inp.get("sds_id")

    return {
        "log": [f"{UNISPSC_CODE}:verify_specifications"],
        "purity_grade": purity,
        "safety_data_sheet_verified": bool(sds_id),
    }


def assessment_engine(state: State) -> dict[str, Any]:
    """Evaluates hazard classifications and storage requirements."""
    inp = state.get("input") or {}
    flash_point = inp.get("flash_point_c", 100)

    # Simple logic to determine hazard and quarantine needs
    if flash_point < 23:
        h_class = "Class 3: Flammable Liquid"
        q_status = "STRICT_ISOLATION"
    elif inp.get("toxic"):
        h_class = "Class 6: Toxic Substance"
        q_status = "CONTROLLED_ACCESS"
    else:
        h_class = "General Chemical"
        q_status = "STANDARD_STORAGE"

    return {
        "log": [f"{UNISPSC_CODE}:assessment_engine"],
        "hazard_class": h_class,
        "quarantine_status": q_status,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Assembles the final chemical certification payload."""
    sds_ok = state.get("safety_data_sheet_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "purity": state.get("purity_grade"),
            "hazard": state.get("hazard_class"),
            "storage_protocol": state.get("quarantine_status"),
            "compliance_met": sds_ok,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("verify", verify_specifications)
_g.add_node("assess", assessment_engine)
_g.add_node("finalize", finalize_certification)

_g.add_edge(START, "verify")
_g.add_edge("verify", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
