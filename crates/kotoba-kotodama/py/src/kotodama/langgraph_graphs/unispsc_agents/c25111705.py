# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111705 — Vessel (segment 25).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111705"
UNISPSC_TITLE = "Vessel"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111705"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Vessel
    vessel_class: str
    displacement_tons: int
    hull_verified: bool
    registry_id: str
    seaworthiness_certified: bool


def inspect_vessel(state: State) -> dict[str, Any]:
    """Inspects the physical integrity and class of the vessel."""
    inp = state.get("input") or {}
    v_class = inp.get("class", "Commercial")
    tonnage = int(inp.get("tonnage", 500))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_vessel"],
        "vessel_class": v_class,
        "displacement_tons": tonnage,
        "hull_verified": tonnage > 0,
    }


def register_vessel(state: State) -> dict[str, Any]:
    """Processes the maritime registry for the inspected vessel."""
    v_class = state.get("vessel_class", "Commercial")
    tonnage = state.get("displacement_tons", 0)
    reg_id = f"IMO-{v_class[:3].upper()}-{tonnage:07d}"

    return {
        "log": [f"{UNISPSC_CODE}:register_vessel"],
        "registry_id": reg_id,
        "seaworthiness_certified": state.get("hull_verified", False),
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Finalizes the vessel manifest and operational status."""
    certified = state.get("seaworthiness_certified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "registry": state.get("registry_id"),
            "operational": certified,
            "status": "ready_for_service" if certified else "under_maintenance",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_vessel", inspect_vessel)
_g.add_node("register_vessel", register_vessel)
_g.add_node("finalize_manifest", finalize_manifest)

_g.add_edge(START, "inspect_vessel")
_g.add_edge("inspect_vessel", "register_vessel")
_g.add_edge("register_vessel", finalize_manifest)
_g.add_edge("finalize_manifest", END)

graph = _g.compile()
