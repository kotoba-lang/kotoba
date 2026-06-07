# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25201516 — Canopy (segment 25).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201516"
UNISPSC_TITLE = "Canopy"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201516"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Canopy vehicle components
    frame_material: str
    load_capacity_kg: int
    weather_seal_verified: bool
    structural_integrity_score: float


def validate_canopy_spec(state: State) -> dict[str, Any]:
    """Initial validation of canopy configuration and intended materials."""
    inp = state.get("input") or {}
    material = inp.get("material", "reinforced-fiberglass")
    return {
        "log": [f"{UNISPSC_CODE}:validate_canopy_spec"],
        "frame_material": material,
        "load_capacity_kg": inp.get("max_load_kg", 250),
    }


def verify_structural_integrity(state: State) -> dict[str, Any]:
    """Simulate engineering verification for load capacity and sealing."""
    capacity = state.get("load_capacity_kg", 0)
    material = state.get("frame_material", "")

    # Calculate integrity heuristic
    integrity = 0.99 if material == "aluminum" else 0.92
    sealing_status = capacity <= 500  # Verification logic

    return {
        "log": [f"{UNISPSC_CODE}:verify_structural_integrity"],
        "structural_integrity_score": integrity,
        "weather_seal_verified": sealing_status,
    }


def finalize_canopy_record(state: State) -> dict[str, Any]:
    """Prepares the finalized manifest for the canopy component."""
    is_verified = (
        state.get("structural_integrity_score", 0) > 0.9 and
        state.get("weather_seal_verified")
    )

    return {
        "log": [f"{UNISPSC_CODE}:finalize_canopy_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification_status": "PASS" if is_verified else "FAIL",
            "spec_summary": {
                "material": state.get("frame_material"),
                "max_load": state.get("load_capacity_kg"),
                "integrity_score": state.get("structural_integrity_score"),
            },
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_canopy_spec)
_g.add_node("verify", verify_structural_integrity)
_g.add_node("finalize", finalize_canopy_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
