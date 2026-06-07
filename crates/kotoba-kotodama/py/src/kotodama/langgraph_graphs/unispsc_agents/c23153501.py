# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153501 — Weld Procurement (segment 23).
Bespoke logic for welding specification validation, certification verification,
and procurement capacity assessment.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153501"
UNISPSC_TITLE = "Weld Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Weld Procurement
    spec_valid: bool
    certifications_met: bool
    capacity_available: bool
    procurement_status: str


def validate_spec(state: State) -> dict[str, Any]:
    """Validates technical welding specifications (materials, joint types, thickness)."""
    inp = state.get("input") or {}
    spec = inp.get("spec", {})
    # Expecting material, weld_type, and thickness in specs
    valid = all(k in spec for k in ["material", "weld_type", "thickness"])
    return {
        "log": [f"{UNISPSC_CODE}:validate_spec"],
        "spec_valid": valid,
    }


def verify_certifications(state: State) -> dict[str, Any]:
    """Verifies that required AWS/ASME certifications are provided and active."""
    if not state.get("spec_valid"):
        return {
            "log": [f"{UNISPSC_CODE}:verify_certifications:skipped"],
            "certifications_met": False,
        }

    inp = state.get("input") or {}
    certs = inp.get("certifications", [])
    # Requirement: at least one recognized certification must be present
    met = len(certs) > 0
    return {
        "log": [f"{UNISPSC_CODE}:verify_certifications"],
        "certifications_met": met,
    }


def assess_capacity(state: State) -> dict[str, Any]:
    """Assess if the procurement volume fits within current manufacturing capacity."""
    if not state.get("certifications_met"):
        return {
            "log": [f"{UNISPSC_CODE}:assess_capacity:denied"],
            "capacity_available": False,
            "procurement_status": "rejected_compliance",
        }

    inp = state.get("input") or {}
    quantity = inp.get("quantity", 0)
    # Mock capacity check: limit to 1000 units for this specific agent
    available = 0 < quantity <= 1000
    return {
        "log": [f"{UNISPSC_CODE}:assess_capacity"],
        "capacity_available": available,
        "procurement_status": "cleared" if available else "over_capacity",
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement request and generates the outcome DID document."""
    ok = state.get("capacity_available", False)
    status = state.get("procurement_status", "failed")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": status,
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_spec", validate_spec)
_g.add_node("verify_certifications", verify_certifications)
_g.add_node("assess_capacity", assess_capacity)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_spec")
_g.add_edge("validate_spec", "verify_certifications")
_g.add_edge("verify_certifications", "assess_capacity")
_g.add_edge("assess_capacity", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
