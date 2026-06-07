# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25181702 — Trailer (segment 25).

Bespoke logic for trailer asset management, covering specification validation,
safety compliance checking, and asset record finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25181702"
UNISPSC_TITLE = "Trailer"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25181702"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Trailer asset
    axle_count: int
    max_payload_kg: float
    safety_check_passed: bool
    hitch_type: str


def validate_specs(state: State) -> dict[str, Any]:
    """Extracts and validates trailer hardware specifications."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "axle_count": int(inp.get("axle_count", 2)),
        "max_payload_kg": float(inp.get("max_payload", 15000.0)),
        "hitch_type": str(inp.get("hitch_type", "kingpin")),
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Checks the trailer configuration against safety weight-per-axle limits."""
    axles = state.get("axle_count", 1)
    payload = state.get("max_payload_kg", 0.0)

    # Assume 8000kg limit per axle for compliance simulation
    compliance = payload <= (axles * 8000.0)

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance(safe={compliance})"],
        "safety_check_passed": compliance,
    }


def finalize_asset_record(state: State) -> dict[str, Any]:
    """Produces the final actor state with registry-ready metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "axles": state.get("axle_count"),
            "safety_status": "CERTIFIED" if state.get("safety_check_passed") else "INSPECT_REQUIRED",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("verify_compliance", verify_compliance)
_g.add_node("finalize_asset_record", finalize_asset_record)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "verify_compliance")
_g.add_edge("verify_compliance", "finalize_asset_record")
_g.add_edge("finalize_asset_record", END)

graph = _g.compile()
