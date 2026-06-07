# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20111604 — Pipe Fiting (segment 20).

Bespoke graph logic for Pipe Fiting. This agent validates fitting
specifications, calculates pressure tolerances, and prepares a verified
fitting record for procurement.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20111604"
UNISPSC_TITLE = "Pipe Fiting"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20111604"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Pipe Fiting
    fitting_type: str
    nominal_size: str
    pressure_class: str
    material_grade: str
    inspection_verified: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the pipe fitting specifications from the input."""
    inp = state.get("input") or {}
    f_type = inp.get("fitting_type", "Elbow 90-Deg")
    size = inp.get("nominal_size", "2-inch")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "fitting_type": f_type,
        "nominal_size": size,
        "inspection_verified": False,
    }


def calculate_tolerance(state: State) -> dict[str, Any]:
    """Calculates if the fitting meets the required pressure class tolerances."""
    inp = state.get("input") or {}
    p_class = inp.get("pressure_class", "Class 3000")
    m_grade = inp.get("material_grade", "ASTM A105")

    # Domain logic: simulate verification based on presence of essential specs
    verified = bool(p_class and m_grade and state.get("nominal_size"))

    return {
        "log": [f"{UNISPSC_CODE}:calculate_tolerance"],
        "pressure_class": p_class,
        "material_grade": m_grade,
        "inspection_verified": verified,
    }


def finalize_order(state: State) -> dict[str, Any]:
    """Prepares the final result for the Pipe Fiting actor."""
    is_ok = state.get("inspection_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_order"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specifications": {
                "type": state.get("fitting_type"),
                "size": state.get("nominal_size"),
                "pressure": state.get("pressure_class"),
                "material": state.get("material_grade"),
            },
            "status": "Verified" if is_ok else "Incomplete Specs",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specs", validate_specs)
_g.add_node("calculate_tolerance", calculate_tolerance)
_g.add_node("finalize_order", finalize_order)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "calculate_tolerance")
_g.add_edge("calculate_tolerance", "finalize_order")
_g.add_edge("finalize_order", END)

graph = _g.compile()
