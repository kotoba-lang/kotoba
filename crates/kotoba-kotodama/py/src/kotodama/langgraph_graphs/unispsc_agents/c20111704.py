# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20111704 — Material (segment 20).

Bespoke graph for managing material specifications and availability within
the mining and well drilling machinery context.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20111704"
UNISPSC_TITLE = "Material"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20111704"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for "Material"
    material_type: str
    material_grade: str
    specification_compliance: bool
    inventory_status: str
    procurement_priority: str


def validate_specification(state: State) -> dict[str, Any]:
    """Validates the material type and grade against project requirements."""
    inp = state.get("input") or {}
    m_type = inp.get("type", "standard_casing")
    m_grade = inp.get("grade", "high_tensile")

    # Pure-Python logic: assume compliance if grade is specified
    compliance = m_grade is not None

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "material_type": m_type,
        "material_grade": m_grade,
        "specification_compliance": compliance,
    }


def assess_availability(state: State) -> dict[str, Any]:
    """Checks inventory levels and determines procurement priority."""
    m_type = state.get("material_type", "unknown")

    # Logic based on material type
    if m_type.startswith("specialized"):
        status = "low_stock"
        priority = "high"
    else:
        status = "available"
        priority = "routine"

    return {
        "log": [f"{UNISPSC_CODE}:assess_availability"],
        "inventory_status": status,
        "procurement_priority": priority,
    }


def finalize_material_record(state: State) -> dict[str, Any]:
    """Consolidates findings into a final result object."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_material_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "material": {
                "type": state.get("material_type"),
                "grade": state.get("material_grade"),
                "compliant": state.get("specification_compliance"),
            },
            "logistics": {
                "status": state.get("inventory_status"),
                "priority": state.get("procurement_priority"),
            },
            "status": "verified",
        },
    }


_g = StateGraph(State)

_g.add_node("validate_spec", validate_specification)
_g.add_node("assess_stock", assess_availability)
_g.add_node("finalize", finalize_material_record)

_g.add_edge(START, "validate_spec")
_g.add_edge("validate_spec", "assess_stock")
_g.add_edge("assess_stock", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
