# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13102003 — Commodity (segment 13).

This bespoke agent manages the lifecycle of raw material commodities, specifically
focusing on resins and elastomeric materials within Segment 13.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13102003"
UNISPSC_TITLE = "Commodity"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13102003"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Segment 13 Commodities
    spec_grade: str
    purity_confirmed: bool
    viscosity_measured: float
    msds_compliant: bool


def validate_specification(state: State) -> dict[str, Any]:
    """Validates the input specification for the commodity batch."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "industrial")
    has_msds = inp.get("msds_provided", False)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "spec_grade": grade,
        "msds_compliant": has_msds,
    }


def perform_assay(state: State) -> dict[str, Any]:
    """Simulates a quality assurance assay on the material sample."""
    grade = state.get("spec_grade", "industrial")
    # Base purity threshold on required grade
    purity = 0.995 if grade == "medical" else 0.940
    # Simulate viscosity measurement based on input characteristics
    viscosity = 120.5 if "resin" in str(state.get("input", "")).lower() else 45.2

    return {
        "log": [f"{UNISPSC_CODE}:perform_assay"],
        "purity_confirmed": purity >= 0.940,
        "viscosity_measured": viscosity,
    }


def certify_batch(state: State) -> dict[str, Any]:
    """Finalizes the commodity certification and emits the formal result."""
    is_valid = (
        state.get("purity_confirmed", False) and
        state.get("msds_compliant", False) and
        state.get("viscosity_measured", 0) > 0
    )

    return {
        "log": [f"{UNISPSC_CODE}:certify_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "CERTIFIED" if is_valid else "REJECTED",
            "metadata": {
                "grade": state.get("spec_grade"),
                "purity_check": state.get("purity_confirmed"),
                "viscosity": state.get("viscosity_measured"),
            },
            "ok": is_valid,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specification)
_g.add_node("assay", perform_assay)
_g.add_node("certify", certify_batch)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assay")
_g.add_edge("assay", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
