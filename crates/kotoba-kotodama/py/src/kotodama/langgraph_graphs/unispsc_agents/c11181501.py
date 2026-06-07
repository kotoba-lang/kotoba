# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11181501 — Fluid Procurement.
Bespoke logic for mineral and mining fluid resource management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11181501"
UNISPSC_TITLE = "Fluid Procurement"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11181501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Fluid Procurement
    source_facility_id: str
    volume_liters: float
    fluid_specification_id: str
    quality_verified: bool
    procurement_status: str


def validate_procurement_request(state: State) -> dict[str, Any]:
    """Validates the incoming fluid procurement request and extracts parameters."""
    inp = state.get("input") or {}
    vol = float(inp.get("volume", 0.0))
    facility = str(inp.get("facility_id", "UNKNOWN-FACILITY"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_procurement_request"],
        "volume_liters": vol,
        "source_facility_id": facility,
        "fluid_specification_id": inp.get("spec_id", "STD-FLUID-01"),
        "procurement_status": "VALIDATED" if vol > 0 else "INVALID_VOLUME"
    }


def analyze_fluid_quality(state: State) -> dict[str, Any]:
    """Simulates a quality check for the requested fluid specification."""
    spec = state.get("fluid_specification_id", "")
    # Simulation: specs starting with 'STD' are pre-verified
    verified = spec.startswith("STD")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_fluid_quality"],
        "quality_verified": verified,
        "procurement_status": "QUALITY_CHECKED" if verified else "QUALITY_PENDING"
    }


def finalize_procurement_log(state: State) -> dict[str, Any]:
    """Finalizes the procurement state and prepares the result output."""
    is_ok = state.get("quality_verified", False) and state.get("volume_liters", 0) > 0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_log"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_id": f"PROC-{UNISPSC_CODE}-{id(state) % 10000}",
            "status": "COMPLETED" if is_ok else "FAILED",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_procurement_request)
_g.add_node("analyze", analyze_fluid_quality)
_g.add_node("finalize", finalize_procurement_log)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
