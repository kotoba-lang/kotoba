# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25174106 — Sunroof (segment 25).

This agent handles state transitions for the inspection, sealing verification,
and final configuration of automotive sunroof components.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174106"
UNISPSC_TITLE = "Sunroof"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174106"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state fields for Sunroof
    mechanism_type: str  # e.g., 'panoramic', 'pop-up', 'spoiler'
    seal_integrity_score: float
    electronic_calibration_ok: bool
    safety_anti_pinch_active: bool


def inspect_mechanism(state: State) -> dict[str, Any]:
    """Inspects the sunroof type and initializes safety parameters."""
    inp = state.get("input") or {}
    mech_type = inp.get("mechanism_type", "standard_electric")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_mechanism"],
        "mechanism_type": mech_type,
        "safety_anti_pinch_active": True
    }


def verify_environmental_seal(state: State) -> dict[str, Any]:
    """Simulates a pressure and leak test on the sunroof seals."""
    # Logic simulating high-quality seal verification
    score = 0.98 if state.get("mechanism_type") != "manual" else 0.95

    return {
        "log": [f"{UNISPSC_CODE}:verify_environmental_seal"],
        "seal_integrity_score": score,
        "electronic_calibration_ok": True
    }


def finalize_sunroof_asset(state: State) -> dict[str, Any]:
    """Aggregates all inspection data into the final result."""
    is_ok = (state.get("seal_integrity_score", 0) > 0.90 and
             state.get("electronic_calibration_ok", False))

    return {
        "log": [f"{UNISPSC_CODE}:finalize_sunroof_asset"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "quality_metrics": {
                "seal_score": state.get("seal_integrity_score"),
                "mechanism": state.get("mechanism_type"),
                "safety_verified": state.get("safety_anti_pinch_active")
            },
            "status": "certified" if is_ok else "failed_inspection"
        }
    }


_g = StateGraph(State)

_g.add_node("inspect_mechanism", inspect_mechanism)
_g.add_node("verify_environmental_seal", verify_environmental_seal)
_g.add_node("finalize_sunroof_asset", finalize_sunroof_asset)

_g.add_edge(START, "inspect_mechanism")
_g.add_edge("inspect_mechanism", "verify_environmental_seal")
_g.add_edge("verify_environmental_seal", "finalize_sunroof_asset")
_g.add_edge("finalize_sunroof_asset", END)

graph = _g.compile()
