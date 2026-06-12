# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13102030 — Commodity (segment 13).

Bespoke graph logic for Segment 13: Resinous and Oily Materials and Rubber and Gums.
This implementation focuses on material specification verification and batch
traceability for resinous commodities.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13102030"
UNISPSC_TITLE = "Commodity"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13102030"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    specification_compliant: bool
    batch_lot_id: str
    viscosity_index: float
    hazard_class_verified: bool


def validate_spec(state: State) -> dict[str, Any]:
    """Validate technical specifications for the resinous material."""
    inp = state.get("input") or {}
    viscosity = float(inp.get("viscosity", 0.0))
    # Requirement: Segment 13 materials must have defined viscosity and hazard profile
    is_compliant = viscosity > 0 and "hazard_data" in inp
    return {
        "log": [f"{UNISPSC_CODE}:validate_spec"],
        "specification_compliant": is_compliant,
        "viscosity_index": viscosity,
        "hazard_class_verified": "hazard_data" in inp,
    }


def assign_traceability(state: State) -> dict[str, Any]:
    """Assign a tracking lot ID for the commodity batch."""
    inp = state.get("input") or {}
    raw_id = inp.get("lot_hint", "0000")
    lot_id = f"S13-{UNISPSC_CODE}-{raw_id}"
    return {
        "log": [f"{UNISPSC_CODE}:assign_traceability"],
        "batch_lot_id": lot_id,
    }


def emit_manifest(state: State) -> dict[str, Any]:
    """Consolidate the final commodity manifest."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "lot_id": state.get("batch_lot_id"),
            "compliant": state.get("specification_compliant", False),
            "viscosity": state.get("viscosity_index"),
            "status": "ready_for_transport" if state.get("specification_compliant") else "rejected",
        },
    }


_g = StateGraph(State)

_g.add_node("validate_spec", validate_spec)
_g.add_node("assign_traceability", assign_traceability)
_g.add_node("emit_manifest", emit_manifest)

_g.add_edge(START, "validate_spec")
_g.add_edge("validate_spec", "assign_traceability")
_g.add_edge("assign_traceability", "emit_manifest")
_g.add_edge("emit_manifest", END)

graph = _g.compile()
