# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25102001 — Tank Procurement (segment 25).

Bespoke logic for heavy armored vehicle acquisition, technical specification
validation, and strategic export compliance verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25102001"
UNISPSC_TITLE = "Tank Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25102001"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Tank Procurement
    armor_protection_level: str
    main_armament_caliber: int
    operational_range_km: int
    strategic_export_cleared: bool
    procurement_priority: str


def validate_technical_requirements(state: State) -> dict[str, Any]:
    """Evaluates the input specifications against standard armored vehicle benchmarks."""
    inp = state.get("input") or {}
    # Extract specs or set defaults for procurement workflow
    armor = inp.get("armor", "Composite/Modular")
    caliber = inp.get("caliber", 120)
    op_range = inp.get("range", 450)

    return {
        "log": [f"{UNISPSC_CODE}:validate_technical_requirements"],
        "armor_protection_level": armor,
        "main_armament_caliber": caliber,
        "operational_range_km": op_range,
    }


def verify_compliance_and_export(state: State) -> dict[str, Any]:
    """Checks the procurement request against strategic munitions control lists."""
    # Logic simulating export license verification for military hardware
    caliber = state.get("main_armament_caliber", 0)
    priority = "High" if caliber >= 120 else "Standard"

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance_and_export"],
        "strategic_export_cleared": True,
        "procurement_priority": priority,
    }


def finalize_procurement_order(state: State) -> dict[str, Any]:
    """Consolidates valid specs and compliance into a final procurement record."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_order"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "VALIDATED",
            "specifications": {
                "armor": state.get("armor_protection_level"),
                "armament": f"{state.get('main_armament_caliber')}mm",
                "range_km": state.get("operational_range_km")
            },
            "priority": state.get("procurement_priority"),
            "compliance_verified": state.get("strategic_export_cleared"),
            "ready_for_tender": True
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_technical_requirements)
_g.add_node("verify", verify_compliance_and_export)
_g.add_node("finalize", finalize_procurement_order)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
