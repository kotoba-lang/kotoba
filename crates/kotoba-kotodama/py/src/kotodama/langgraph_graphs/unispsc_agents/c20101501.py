# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20101501 — Housing.
Bespoke implementation for Mining and Well Drilling segment housing logistics.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20101501"
UNISPSC_TITLE = "Housing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20101501"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Housing
    structure_type: str        # e.g., "modular_cabin", "container_unit"
    capacity_count: int        # number of personnel
    hvac_ready: bool           # climate control status
    safety_inspection: bool    # fire/safety compliance
    deployment_zone: str       # rig site or mining camp ID


def assess_requirements(state: State) -> dict[str, Any]:
    """Evaluates the housing request and determines basic configuration."""
    inp = state.get("input") or {}
    capacity = inp.get("personnel_count", 1)
    zone = inp.get("site_id", "unassigned")

    return {
        "log": [f"{UNISPSC_CODE}:assess_requirements"],
        "capacity_count": capacity,
        "deployment_zone": zone,
        "structure_type": "industrial_modular" if capacity > 4 else "compact_sleeper"
    }


def configure_unit(state: State) -> dict[str, Any]:
    """Applies engineering specs to the housing unit based on the zone."""
    zone = state.get("deployment_zone", "unassigned")
    # Arctic or desert conditions based on zone prefix (logic simulation)
    extreme_environment = zone.startswith("ARC") or zone.startswith("DES")

    return {
        "log": [f"{UNISPSC_CODE}:configure_unit"],
        "hvac_ready": True,
        "safety_inspection": True if extreme_environment else False
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Finalizes the housing assignment and prepares the result payload."""
    ready = state.get("safety_inspection", False) and state.get("hvac_ready", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "assignment": {
                "type": state.get("structure_type"),
                "capacity": state.get("capacity_count"),
                "zone": state.get("deployment_zone"),
                "status": "READY" if ready else "PENDING_INSPECTION"
            },
            "ok": True
        }
    }


_g = StateGraph(State)

_g.add_node("assess_requirements", assess_requirements)
_g.add_node("configure_unit", configure_unit)
_g.add_node("finalize_inventory", finalize_inventory)

_g.add_edge(START, "assess_requirements")
_g.add_edge("assess_requirements", "configure_unit")
_g.add_edge("configure_unit", "finalize_inventory")
_g.add_edge("finalize_inventory", END)

graph = _g.compile()
