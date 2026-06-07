# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121112 — Reducer (segment 20).

This bespoke LangGraph implementation handles the technical specification
validation for industrial pipe reducers used in mining and drilling operations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121112"
UNISPSC_TITLE = "Reducer"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121112"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    inlet_size_mm: float
    outlet_size_mm: float
    material_grade: str
    pressure_rating_psi: int
    compliance_verified: bool


def validate_dimensions(state: State) -> dict[str, Any]:
    """Ensures inlet is larger than outlet and both are positive."""
    inp = state.get("input") or {}
    inlet = float(inp.get("inlet_size_mm", 0.0))
    outlet = float(inp.get("outlet_size_mm", 0.0))

    is_valid = inlet > outlet and outlet > 0
    log_msg = f"{UNISPSC_CODE}:validate_dimensions -> Inlet:{inlet}mm, Outlet:{outlet}mm, Valid:{is_valid}"

    return {
        "log": [log_msg],
        "inlet_size_mm": inlet,
        "outlet_size_mm": outlet,
        "compliance_verified": is_valid
    }


def assess_pressure_compliance(state: State) -> dict[str, Any]:
    """Checks if the material grade is sufficient for the specified pressure rating."""
    inp = state.get("input") or {}
    rating = int(inp.get("pressure_rating_psi", 0))
    material = str(inp.get("material_grade", "Standard Carbon Steel"))

    # Mining safety logic: High pressure (>5000 PSI) requires Alloy or Stainless
    is_safe = True
    if rating > 5000 and "Carbon" in material:
        is_safe = False

    log_msg = f"{UNISPSC_CODE}:assess_pressure_compliance -> PSI:{rating}, Mat:{material}, Safe:{is_safe}"

    return {
        "log": [log_msg],
        "material_grade": material,
        "pressure_rating_psi": rating,
        "compliance_verified": state.get("compliance_verified", False) and is_safe
    }


def compile_manufacturing_specs(state: State) -> dict[str, Any]:
    """Finalizes the component data for the result dictionary."""
    is_ok = state.get("compliance_verified", False)
    log_msg = f"{UNISPSC_CODE}:compile_manufacturing_specs -> Verified:{is_ok}"

    return {
        "log": [log_msg],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "inlet_mm": state.get("inlet_size_mm"),
                "outlet_mm": state.get("outlet_size_mm"),
                "material": state.get("material_grade"),
                "max_psi": state.get("pressure_rating_psi"),
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_dimensions", validate_dimensions)
_g.add_node("assess_pressure_compliance", assess_pressure_compliance)
_g.add_node("compile_manufacturing_specs", compile_manufacturing_specs)

_g.add_edge(START, "validate_dimensions")
_g.add_edge("validate_dimensions", "assess_pressure_compliance")
_g.add_edge("assess_pressure_compliance", "compile_manufacturing_specs")
_g.add_edge("compile_manufacturing_specs", END)

graph = _g.compile()
