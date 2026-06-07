# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24111811 — Carboy (segment 24).
Bespoke graph logic for specialized liquid container management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24111811"
UNISPSC_TITLE = "Carboy"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24111811"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Carboy
    capacity_liters: float
    material_composition: str
    is_hazardous_rated: bool
    seal_integrity_score: float
    batch_tracking_id: str


def inspect_specifications(state: State) -> dict[str, Any]:
    """Validates the carboy's physical specifications and material safety."""
    inp = state.get("input") or {}
    capacity = float(inp.get("capacity", 20.0))
    material = str(inp.get("material", "High-Density Polyethylene"))
    is_haz = "acid" in material.lower() or inp.get("hazardous", False)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "capacity_liters": capacity,
        "material_composition": material,
        "is_hazardous_rated": is_haz,
    }


def verify_containment(state: State) -> dict[str, Any]:
    """Simulates leak testing and structural integrity verification."""
    # Logic based on material and capacity
    score = 0.99 if state.get("capacity_liters", 0) <= 50.0 else 0.95
    batch_id = f"CB-{UNISPSC_CODE}-{int(score * 1000)}"

    return {
        "log": [f"{UNISPSC_CODE}:verify_containment"],
        "seal_integrity_score": score,
        "batch_tracking_id": batch_id,
    }


def finalize_asset_record(state: State) -> dict[str, Any]:
    """Produces the final diagnostic and manifest for the Carboy asset."""
    status = "certified" if state.get("seal_integrity_score", 0) > 0.90 else "quarantine"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "asset_id": state.get("batch_tracking_id"),
            "compliance_status": status,
            "specs": {
                "material": state.get("material_composition"),
                "volume": state.get("capacity_liters"),
                "hazmat": state.get("is_hazardous_rated")
            },
            "ok": status == "certified"
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_specifications)
_g.add_node("verify", verify_containment)
_g.add_node("finalize", finalize_asset_record)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
