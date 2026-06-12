# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24111810 — Water Tank (segment 24).
Bespoke logic for water tank specifications and quality assurance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24111810"
UNISPSC_TITLE = "Water Tank"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24111810"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Water Tank
    capacity_liters: int
    material_spec: str
    quality_inspection_passed: bool
    installation_site_ready: bool


def validate_spec(state: State) -> dict[str, Any]:
    """Extracts and validates the tank specification from input."""
    inp = state.get("input") or {}
    capacity = inp.get("capacity", 1000)
    material = inp.get("material", "HDPE")
    site_ready = inp.get("site_ready", False)

    return {
        "log": [f"{UNISPSC_CODE}:validate_spec:capacity={capacity}:material={material}"],
        "capacity_liters": capacity,
        "material_spec": material,
        "installation_site_ready": site_ready,
    }


def inspect_tank(state: State) -> dict[str, Any]:
    """Performs a simulated quality inspection based on material standards."""
    material = state.get("material_spec", "HDPE")
    # Simulation logic: only certain materials pass the default quality check
    standard_materials = {"HDPE", "STEEL", "CONCRETE", "FIBERGLASS"}
    passed = material.upper() in standard_materials

    return {
        "log": [f"{UNISPSC_CODE}:inspect_tank:passed={passed}"],
        "quality_inspection_passed": passed,
    }


def provision_tank(state: State) -> dict[str, Any]:
    """Finalizes the procurement state based on inspection and site readiness."""
    inspection_ok = state.get("quality_inspection_passed", False)
    site_ok = state.get("installation_site_ready", False)
    ready_for_delivery = inspection_ok and site_ok

    return {
        "log": [f"{UNISPSC_CODE}:provision_tank:ready={ready_for_delivery}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "capacity": state.get("capacity_liters"),
                "material": state.get("material_spec"),
            },
            "status": "ready_for_delivery" if ready_for_delivery else "pending_requirements",
            "ok": ready_for_delivery,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_spec", validate_spec)
_g.add_node("inspect_tank", inspect_tank)
_g.add_node("provision_tank", provision_tank)

_g.add_edge(START, "validate_spec")
_g.add_edge("validate_spec", "inspect_tank")
_g.add_edge("inspect_tank", "provision_tank")
_g.add_edge("provision_tank", END)

graph = _g.compile()
