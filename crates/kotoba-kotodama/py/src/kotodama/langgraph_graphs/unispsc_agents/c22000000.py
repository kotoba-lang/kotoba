# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22000000 — Construction (segment 22).

This bespoke LangGraph implementation handles construction-specific logic
including permit verification, safety clearance, and resource allocation
modeling for the Etz Hayyim actor network.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22000000"
UNISPSC_TITLE = "Construction"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22000000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Construction
    permits_approved: bool
    safety_clearance: str
    materials_staged: list[str]
    site_ready: bool


def validate_permits(state: State) -> dict[str, Any]:
    """Validates site permits and safety standards."""
    inp = state.get("input") or {}
    permit_id = inp.get("permit_id", "PENDING")
    is_valid = permit_id.startswith("PRMT-")

    return {
        "log": [f"{UNISPSC_CODE}:validate_permits"],
        "permits_approved": is_valid,
        "safety_clearance": "HIGH_CONFIDENCE" if is_valid else "QUARANTINED",
    }


def schedule_resources(state: State) -> dict[str, Any]:
    """Allocates machinery and materials based on project scope."""
    inp = state.get("input") or {}
    project_scale = inp.get("scale", "standard")

    inventory = ["structural_steel", "concrete_mix"]
    if project_scale == "industrial":
        inventory.extend(["heavy_cranes", "excavators"])

    return {
        "log": [f"{UNISPSC_CODE}:schedule_resources"],
        "materials_staged": inventory,
        "site_ready": state.get("permits_approved", False),
    }


def finalize_construction_manifest(state: State) -> dict[str, Any]:
    """Compiles the final construction actor manifest."""
    is_ready = state.get("site_ready", False)
    clearance = state.get("safety_clearance", "UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "READY_FOR_BREAKING_GROUND" if is_ready else "HOLD_FOR_APPROVAL",
            "safety_protocol": clearance,
            "inventory_count": len(state.get("materials_staged", [])),
            "ok": is_ready,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_permits)
_g.add_node("schedule", schedule_resources)
_g.add_node("finalize", finalize_construction_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "schedule")
_g.add_edge("schedule", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
